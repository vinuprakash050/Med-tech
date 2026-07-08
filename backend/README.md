# Medicine Alternative Recommendation Backend

Lightweight production-style FastAPI backend prototype for recommending lower-cost equivalent medicines using a single `medicines` table, openFDA enrichment, rule-based validation, and an LLM reasoning layer.

## Stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy ORM with async support
- Alembic
- Pydantic DTOs

## Project Structure

```text
backend/
├── app/
│   ├── api/routes/
│   ├── core/
│   ├── dto/
│   ├── integrations/
│   ├── models/
│   ├── prompts/
│   ├── providers/
│   ├── repositories/
│   ├── services/
│   ├── utils/
│   └── main.py
├── alembic/
├── scripts/
├── requirements.txt
├── .env.example
└── README.md
```

## Core Logic

All medicines live in one `medicines` table. Alternatives are discovered dynamically by matching:

- same `salt_composition`
- same `dosage`
- lower `price`
- optional generic preference

The service excludes the requested medicine itself, validates salt and dosage consistency, and then asks the configured LLM provider to produce concise reasoning using only database-supplied data.

When available, the service also enriches medicine metadata from the official openFDA product label API and stores the normalized fields back into PostgreSQL.
Search is DB-first: the backend first resolves likely medicine names from PostgreSQL using normalized partial matching and `difflib` similarity, then uses the LLM only to choose among DB candidates.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add these optional variables to `.env` if you want to use openFDA with an API key:

```bash
OPENFDA_BASE_URL=https://api.fda.gov
OPENFDA_API_KEY=
```

Create PostgreSQL database:

```sql
CREATE DATABASE medicine_db;
```

## Migrations

Generate a migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

## Seed Data

```bash
python -m scripts.seed_data
```

## Run Server

```bash
uvicorn app.main:app --reload
```

## API Endpoints

- `GET /health`
- `GET /api/v1/medicines`
- `POST /api/v1/medicine/recommend`
- `POST /api/v1/medicine/suggest`
- `POST /api/v1/medicine/enrich`

Sample request:

```json
{
  "medicine_name": "Dolo 650",
  "generic_preference": true
}
```

Suggestion request:

```json
{
  "query": "paracitamol"
}
```

Enrichment request:

```json
{
  "medicine_name": "Dolo 650"
}
```

## Run with `uv`

You can now start the app with:

```bash
cd backend
. .venv/bin/activate
uv run run.py
```

This file runs Alembic migrations automatically before the FastAPI app starts.

> If your shell already has `DATABASE_URL` set from another project, that value will override `.env`. In that case either unset it or explicitly export the project's URL before running:

```bash
unset DATABASE_URL
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/medicine_db"
uv run run.py
```

Sample response shape:

```json
{
  "requested_medicine": {
    "name": "Dolo 650",
    "fda_data_available": true,
    "active_ingredients": "Paracetamol"
  },
  "recommended_alternatives": [],
  "llm_reasoning": "These alternatives have the same composition and dosage...",
  "safety_validation": {
    "same_salt": true,
    "same_dosage": true
  }
}
```

Enrichment response shape:

```json
{
  "medicine": {},
  "openfda_data_found": true,
  "enriched_fields": ["generic_name", "active_ingredients"]
}
```

## Provider Layer

Supported provider abstractions:

- `openai`
- `gemini`
- `groq`
- `openrouter`
- `mock`

Switch providers using `LLM_PROVIDER`. `mock` works out of the box for local development. `openai`, `gemini`, `groq`, and `openrouter` use direct async HTTP calls when their API keys and model names are configured.

openFDA uses its own optional API key and otherwise falls back to public requests.

## Recommendation Flow

1. Normalize the user input.
2. Resolve likely medicine candidates from PostgreSQL with partial matching and `difflib`.
3. Ask the LLM to choose the most likely candidate from DB-provided names only.
4. Load the resolved medicine record.
5. Query the same `medicines` table for approved records with the same salt composition and dosage.
6. Exclude the original medicine.
7. Prefer cheaper medicines and optionally rank generic products first.
8. Enrich requested medicine and alternatives from openFDA when metadata is missing or stale.
9. Build a prompt from database facts plus stored openFDA facts only.
10. Return structured recommendations and reasoning.

## Notes

- No OCR
- No vendors
- No authentication
- No separate alternatives table
- No vector database
- No LangChain or CrewAI
