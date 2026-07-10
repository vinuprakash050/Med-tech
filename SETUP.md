# Med-tech Setup Guide — From Scratch

## Prerequisites

### 1. Install Python 3.11+
Download from https://www.python.org/downloads/
- During install: check **"Add Python to PATH"**
- Verify:
  ```
  python --version
  ```

### 2. Install Node.js 18+
Download from https://nodejs.org/en/download (LTS version)
- Verify:
  ```
  node --version
  npm --version
  ```

### 3. Install PostgreSQL 15+
Download from https://www.postgresql.org/download/
- Remember the **postgres superuser password** you set during install
- Default port: `5432`
- Verify (in psql shell or pgAdmin):
  ```sql
  SELECT version();
  ```

---

## Step 1 — Clone the repo

```bash
git clone git@github.com:vinuprakash050/Med-tech.git
cd Med-tech
```

---

## Step 2 — Create the database

Open **psql** (or pgAdmin) and run:

```sql
CREATE DATABASE medicine_db;
```

Or from the terminal:

```bash
psql -U postgres -c "CREATE DATABASE medicine_db;"
```

---

## Step 3 — Backend setup

```bash
cd backend
```

### 3a. Create and activate virtual environment

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / WSL / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3b. Install Python dependencies

```bash
pip install -r requirements.txt
```

> Note: `easyocr` and `opencv-python` are large packages — this may take a few minutes.

### 3c. Create the `.env` file

Copy the example and fill in your values:

```bash
# Windows CMD
copy .env.example .env

# Linux / WSL / macOS
cp .env.example .env
```

Edit `.env` with your actual values:

```env
APP_NAME="Medicine Alternative Recommendation API"
APP_VERSION="0.1.0"
APP_ENV="development"
DEBUG=true
API_V1_PREFIX="/api/v1"

# PostgreSQL — update user/password to match your install
DATABASE_URL="postgresql+asyncpg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/medicine_db"

# LLM provider — set to "mock" for offline testing, or "openrouter" for live AI
LLM_PROVIDER="openrouter"
LLM_MODEL="openrouter/auto"

# API keys — fill in whichever provider you are using
OPENROUTER_API_KEY="your-openrouter-api-key"
OPENAI_API_KEY=""
GEMINI_API_KEY=""
GROQ_API_KEY=""

CORS_ORIGINS='["*"]'
LOG_LEVEL="INFO"
```

### 3d. Run database migrations

```bash
alembic upgrade head
```

### 3e. Seed the database

There are two seed scripts. Run them in this order:

**Option A — Seed from JSON (recommended, uses `app/data/medicines.json`):**
```bash
python scripts/seed_data.py
```

**Option B — Seed from hardcoded list (fallback, ~90 Indian brand medicines):**
```bash
python scripts/seed_medicines.py
```

> You only need to run one. `seed_data.py` is the primary script and reads from the
> curated JSON file. `seed_medicines.py` is a standalone fallback if the JSON is missing.
> Both scripts **wipe the existing medicines table** before inserting, so re-running is safe.

Expected output:
```
✅ Seeded 90 unique medicines successfully
```

### 3f. Start the backend server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs available at: http://localhost:8000/docs

---

## Step 4 — Frontend setup

Open a **new terminal** and:

```bash
cd Med-tech/frontend
```

### 4a. Install Node dependencies

```bash
npm install
```

### 4b. Create the `.env` file

```bash
# Windows CMD
echo VITE_API_BASE=http://localhost:8000 > .env

# Linux / WSL / macOS
echo "VITE_API_BASE=http://localhost:8000" > .env
```

> For LAN / mobile access, replace `localhost` with your Wi-Fi IP (e.g. `http://10.20.0.64:8000`).
> Find your IP with `ipconfig` (Windows) or `ip a` (Linux).

### 4c. Start the frontend dev server

```bash
# Local only
npm run dev

# Accessible from other devices on the same network (mobile, teammates)
npm run dev -- --host
```

App available at: http://localhost:5173

---

## Quick start — both servers together

**Terminal 1 (Backend):**
```bash
cd Med-tech/backend
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # Linux/macOS
alembic upgrade head                # run once (creates tables)
python scripts/seed_data.py         # run once (populates medicines)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
cd Med-tech/frontend
npm run dev -- --host
```

---

## Verify everything works

| Check | URL |
|---|---|
| Backend health | http://localhost:8000/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend app | http://localhost:5173 |

---

## Troubleshooting

**`ModuleNotFoundError` on backend start**
→ Make sure the virtual environment is activated (`pip list` should show fastapi)

**`ERESOLVE` on `npm install`**
→ Run `npm install --legacy-peer-deps`

**`connection refused` on database**
→ Make sure PostgreSQL service is running:
- Windows: search "Services" → find PostgreSQL → Start
- Linux: `sudo service postgresql start`

**`Cannot find module '@vitejs/plugin-react'`**
→ Run `npm install @vitejs/plugin-react@4 --legacy-peer-deps`

**`seed_data.py` fails with `FileNotFoundError`**
→ Make sure `backend/app/data/medicines.json` exists (it should be in the repo).
→ If missing, run `python scripts/seed_medicines.py` as the fallback instead.

**`alembic upgrade head` fails with `target database is not up to date`**
→ Run `alembic stamp head` then retry `alembic upgrade head`

**Backend reachable from PC but not from mobile**
→ Make sure backend starts with `--host 0.0.0.0`
→ Set `VITE_API_BASE` in frontend `.env` to your Wi-Fi IP (not localhost)
→ Check Windows Firewall allows port 8000 and 5173

---

## New Features — Medical Devices Module

This section documents the device features added in the latest development session.

---

### Overview

A full medical devices module was added alongside the existing medicine search. It covers two distinct experiences:

- **User flow** — device results appear inside the search dropdown as the user types; clicking opens a polished device detail page
- **Vendor flow** — a dedicated Device Feedback Analyser page automatically runs AI analysis on user survey data for every device model

---

### Backend changes

#### 1. Device data (`backend/app/agents/device_data.json`)

A large dummy dataset containing:

- **2 device categories** — Hearing Aid, Pacemaker
- **6 device models** — 3 per category (e.g. ClearSound Pro 360, CardioSync Elite DR)
- **140 user survey feedback entries** — 20–30 reviews per model with ratings and written comments

#### 2. Device DTOs (`backend/app/dto/device.py`)

Pydantic models split by audience:

| Model | Purpose |
|---|---|
| `DeviceModelResponse` | Single model card for users |
| `DeviceResponse` | Full device with all models |
| `DeviceSearchResultItem` | Slim card for search dropdown |
| `DeviceSearchResponse` | Wrapper for search endpoint |
| `FeedbackEntry` | Raw survey response |
| `DeviceFeedbackAnalysis` | AI-generated pros/cons for vendors |

#### 3. Device Feedback Agent (`backend/app/agents/device_feedback_agent.py`)

An LLM agent that receives all survey feedback for a device model and returns structured analysis:

- Sends feedback to the LLM via `generate_response_with_system()`
- Returns: positives list, negatives list, sentiment, summary, top improvement area
- Falls back to keyword heuristic analysis when mock mode or LLM fails
- Uses `lru_cache` JSON loader — same pattern as `vendor_discount_agent`

#### 4. Device routes (`backend/app/api/routes/devices.py`)

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/devices?q=` | Keyword search — returns matching device models |
| `GET /api/v1/devices/all` | Full catalogue — used by vendor page |
| `GET /api/v1/devices/{device_id}` | Single device detail |
| `GET /api/v1/devices/{model_id}/feedback-analysis` | AI feedback analysis for a model |

Router registered in `backend/app/main.py`.

#### 5. Recommendation prompt update (`backend/app/prompts/recommendation.py`)

The "Why these alternatives?" LLM prompt was rewritten to produce a maximum of **3 sentences** as a single flowing paragraph — covering shared salt composition, price saving range, and one standout detail. The previous prompt produced one sentence per medicine which was verbose.

---

### Frontend changes

#### Search page — device results in dropdown

- As the user types, device search fires in parallel with medicine suggestions (debounced 300ms)
- Matching device models appear inside the existing "Did you mean" dropdown under a **Medical Devices** section header
- Each device entry shows: icon, model name, brand badge, price, star rating
- Clicking a device navigates to the device detail page (not the medicine recommendation flow)

#### Device Detail page (user-facing)

Accessed by clicking a device in the search dropdown.

- Full-width blue gradient hero with device icon, model name, brand, star rating, and price
- Two info cards below: **Uses & Indications** and **Unique Characteristics**
- Back button returns to the search page

#### Vendor navigation

Two buttons added to the search page hero (below the genRx logo):

- **Vendor Dashboard** — navigates to `#vendor` (existing medicine expiry/discount planner)
- **Device Feedback** — navigates to `#vendor-devices` (new device feedback analyser)

The same "Device Feedback" button also appears inside the existing Vendor Dashboard hero.

#### Device Feedback Analyser page (vendor-facing)

Accessed via `#vendor-devices`.

- Full-width blue gradient header showing model count and live "analysed" counter
- On load, automatically fires all 6 feedback analysis API calls in parallel — no manual button needed
- Each model card shows a spinner while loading, then displays the full AI analysis:
  - Sentiment badge (Highly Positive / Positive / Mixed / Negative)
  - Review count and average rating
  - AI summary paragraph
  - **What users love** — frequency bars for positive themes
  - **Pain points** — frequency bars for negative themes
  - Top improvement area highlight (yellow box)
- Clicking a card navigates to the device detail page; back button returns to the analyser

#### Vendor Dashboard — pagination

The medicine grid on the vendor dashboard now shows **3 cards per page** with numbered pagination controls and a "Page X of Y · N total" counter.

---

### File summary

| File | Change |
|---|---|
| `backend/app/agents/device_data.json` | New — dummy device + feedback dataset |
| `backend/app/dto/device.py` | New — device DTOs |
| `backend/app/agents/device_feedback_agent.py` | New — AI feedback analysis agent |
| `backend/app/api/routes/devices.py` | New — device API routes |
| `backend/app/main.py` | Updated — registered device router |
| `backend/app/prompts/recommendation.py` | Updated — concise 3-sentence reasoning prompt |
| `frontend/src/App.jsx` | Updated — device search, detail view, vendor devices page, pagination |
| `frontend/src/styles.css` | Updated — all device feature styles |
