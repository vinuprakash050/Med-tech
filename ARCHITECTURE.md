# genRx — System Architecture & Agent Reference

## Overview

genRx is a full-stack AI-powered medicine and medical device platform. It helps users find cheaper medicine alternatives, parse prescriptions, explore medical devices, and gives vendors AI-driven inventory and feedback insights.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser / Mobile                         │
│              React SPA (Vite · localhost:5173)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (port 8000)                     │
│                                                                 │
│  /api/v1/medicine/*     /api/v1/vendor/*     /api/v1/devices/*  │
│  /api/v1/prescription/*                                         │
│                                                                 │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │   Agents     │  │  Integrations  │  │    LLM Providers    │ │
│  │  (AI logic)  │  │   (OpenFDA)    │  │  (pluggable layer)  │ │
│  └──────────────┘  └────────────────┘  └─────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           PostgreSQL (medicine_db)                      │   │
│  │       SQLAlchemy async · Alembic migrations             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
               ┌─────────────────────────┐
               │   External LLM APIs     │
               │  OpenRouter / OpenAI /  │
               │  Gemini / Groq / Azure  │
               └─────────────────────────┘
```

---

## Backend Layer Breakdown

### 1. API Routes (`app/api/routes/`)

| File | Prefix | Responsibility |
|---|---|---|
| `health.py` | `/health` | Liveness check |
| `medicines.py` | `/api/v1/medicine` | Search, recommend, suggest, enrich |
| `prescription.py` | `/api/v1/prescription` | Upload image → parse medicines |
| `vendor.py` | `/api/v1/vendor` | Raw dashboard + AI discount dashboard |
| `devices.py` | `/api/v1/devices` | Device search, detail, feedback analysis |

---

### 2. LLM Provider Layer (`app/providers/`)

All agents talk to LLMs through a single abstract interface. The active provider is resolved at startup from `.env`.

```
BaseLLMProvider (abstract)
├── OpenAIProvider          — OpenAI API (GPT models)
├── GeminiProvider          — Google Gemini
├── GroqProvider            — Groq (fast inference, Llama / Mixtral)
├── OpenRouterProvider      — OpenRouter (routes to any model)
├── AzureOpenAIProvider     — Azure OpenAI (supports vision)
└── MockLLMProvider         — Offline mode, no API key needed
```

**Key interface methods:**

| Method | Purpose |
|---|---|
| `generate_response(prompt)` | Single-turn completion |
| `generate_response_with_system(system, user)` | System + user prompt |
| `generate_response_with_image(system, user, image_bytes)` | Vision (image input) |
| `supports_vision` | Boolean — whether image input is supported |

**Switching providers** — set `LLM_PROVIDER` in `.env`:

```env
LLM_PROVIDER=openrouter   # live AI
LLM_PROVIDER=mock         # offline, no key needed
```

---

## Agents

All agents follow the same pattern:
1. Accept data + an `LLMProvider` instance
2. Build a structured prompt
3. Call the LLM and parse the JSON or prose response
4. Fall back to a heuristic/rule-based result if mock mode or LLM fails

---

### Agent 1 — `PrescriptionParserAgent`
**File:** `app/agents/prescription_parser.py`

**Purpose:** Convert raw OCR text from a prescription image into a structured list of prescribed medicines.

**Input:** Raw OCR string (noisy, multi-line, mixed clinic headers + medicine lines)

**Output:** `PrescriptionParseResult` — patient name, doctor, date, list of `ParsedMedicine` (name, dosage, frequency, duration, confidence)

**How it works:**
- Pre-filters OCR text to strip clinic headers, patient info, phone numbers, and noise before sending to the LLM (reduces tokens and hallucination risk)
- Sends cleaned text to the LLM with a strict JSON schema prompt
- LLM returns structured JSON with medicine entries and confidence scores
- On failure / mock mode: falls back to a regex heuristic that identifies medicine lines by dosage-form prefix (`T.`, `Cap.`, `Syr.`) and dosage markers (`mg`, `BD`, `TID`)

**Fallback:** Two-pass regex extractor — pass 1 uses dosage-form prefixes, pass 2 uses dosage/frequency markers if pass 1 finds nothing.

---

### Agent 2 — `VisionPrescriptionParser`
**File:** `app/agents/vision_prescription_parser.py`

**Purpose:** Parse a prescription image directly using a vision-capable LLM, bypassing EasyOCR entirely.

**Input:** Raw image bytes (JPEG / PNG) + optional OCR text fallback

**Output:** `PrescriptionParseResult` — same schema as `PrescriptionParserAgent`

**How it works:**
- Checks `provider.supports_vision` — if False, delegates to `PrescriptionParserAgent` with the OCR text fallback
- Encodes the image and sends it with a vision-specific system prompt to the LLM
- More accurate than OCR + text parsing for handwritten, tilted, or mixed-format prescriptions
- On LLM failure: falls back to `PrescriptionParserAgent` using the OCR text if provided

**Used when:** Azure OpenAI or any other vision-capable provider is configured.

---

### Agent 3 — `MedicineInsightsAgent`
**File:** `app/agents/medicine_insights_agent.py`

**Purpose:** Generate structured clinical insights for a medicine — summary, key uses, safety points, side effects, who should be careful, pregnancy guidance, and emergency warnings.

**Input:** A `Medicine` ORM model + optional reference medicine (for generic comparison)

**Output:** `MedicineInsightsResponse` — 8 structured fields shown in the medicine detail panel

**How it works:**
- In LLM mode: sends medicine label data (purpose, indications, warnings, adverse reactions) to the LLM with a strict output schema
- Enforces hard limits regardless of LLM output: summary ≤ 20 words, key uses ≤ 5 items × 4 words, safety ≤ 4 items × 12 words, side effects ≤ 4 items × 6 words
- In mock / fallback mode: builds the response directly from DB fields using `_build_fallback_insights()` — never invents facts
- The fallback uses `_split_bullets()` to parse OpenFDA-style inline bullet text (e.g. `"may occur if you take • more than 8 tablets • with alcohol"`) into clean separate points

**Displayed on:** Left panel of the medicine results page — AI Summary, Key Uses, Key Safety, Side Effects, Who Should Be Careful.

---

### Agent 4 — `MedicineRecommendationService`
**File:** `app/agents/medicine_recommendation.py`

**Purpose:** Find cheaper medicine alternatives with the same salt composition and generate a natural-language explanation of why they are safe substitutes.

**Input:** Medicine name string + generic preference boolean

**Output:** `RecommendationResponse` — requested medicine, list of alternatives with price differences, LLM reasoning (2–3 sentences), safety validation

**How it works:**
1. Looks up the requested medicine in PostgreSQL via `MedicineRepository`
2. Falls back to `HybridMedicineSearchService` (fuzzy + semantic search) if exact match fails
3. Queries alternatives with the same salt composition at a lower price
4. Optionally enriches medicines with OpenFDA data
5. Calls the LLM with a prompt asking for a **maximum 3-sentence plain prose explanation** covering: shared salt, price saving range, one standout detail
6. On LLM failure: returns a safe generic fallback sentence
7. Strips markdown from LLM output before returning

**LLM output format:** Plain prose, max 3 sentences. No per-medicine breakdown, no bullet points.

---

### Agent 5 — `VendorDiscountAgent`
**File:** `app/agents/vendor_discount_agent.py`

**Purpose:** Analyse vendor medicine inventory and recommend clearance discounts based on expiry pressure, sales velocity, and stock depth.

**Input:** List of `VendorMedicine` items (from `vendor_data.json`) — each has expiry date, stock, 7-day sales, 30-day sales, margin

**Output:** `VendorDashboardResponse` — summary metrics + per-medicine cards with urgency label, discount %, action, confidence, reason

**How it works:**
1. Calculates a rule-based urgency score per medicine using expiry days, sales rate, and stock level
2. Derives a baseline discount recommendation (0–35%) from the score
3. Sends the baseline to the LLM to refine the reason and adjust the recommendation
4. Runs all 20 medicines concurrently with `asyncio.gather()`
5. Sorts final cards by days until expiry (most urgent first)

**Urgency scoring formula:**
```
urgency = min(100, (120 - days_left) × 0.55 + slow_movement × 0.25 + overstock × 0.15)
```

**Vendor dashboard shows:** 3 cards per page with pagination, summary metrics (medicines tracked, expiring soon, clearance candidates, avg discount).

---

### Agent 6 — `DeviceFeedbackAgent`
**File:** `app/agents/device_feedback_agent.py`

**Purpose:** Analyse a batch of user survey feedback for a medical device model and return structured AI-generated pros/cons for the vendor.

**Input:** `model_id` → loads all feedback entries from `device_data.json` (20–30 reviews per model with ratings and written comments)

**Output:** `DeviceFeedbackAnalysis` — positives list with frequency counts, negatives list with frequency counts, overall sentiment, executive summary, top improvement area

**How it works:**
- Builds a structured prompt from all reviews (rating + comment + date per entry)
- Sends to LLM with a strict JSON schema requesting themed positive/negative groupings with frequency estimates
- On mock / failure: falls back to a keyword scanner that groups positive words in high-rated reviews and negative words in low-rated reviews
- Called automatically on page load for all 6 device models in parallel (no manual button)

**Sentiment levels:** Highly Positive · Positive · Mixed · Negative · Highly Negative

---

## Data Flow — Key User Journeys

### Medicine search
```
User types → suggest API (debounced) → MedicineSuggestionService → DB fuzzy match
User submits → recommend API → MedicineRecommendationService
  → DB lookup → OpenFDA enrichment → MedicineInsightsAgent (fallback)
  → LLM reasoning (max 3 sentences) → RecommendationResponse → frontend
```

### Prescription upload
```
User uploads image → prescription API
  → EasyOCR (text extraction) OR VisionPrescriptionParser (direct image)
  → PrescriptionParserAgent (LLM or heuristic)
  → list of medicine names → each name → recommend API
```

### Device search
```
User types → device search API (debounced, parallel with medicine suggest)
  → keyword match against device_data.json search_keywords
  → DeviceSearchResultItem list → shown in suggestions dropdown
User clicks device → DeviceDetailView (uses, unique characteristics, rating, price)
```

### Vendor device feedback
```
Vendor opens #vendor-devices
  → GET /api/v1/devices/all → all 6 device models loaded
  → 6 parallel GET /api/v1/devices/{model_id}/feedback-analysis calls
  → DeviceFeedbackAgent → LLM analyses survey data → pros/cons per model
  → click any card → DeviceDetailView (user-facing detail page)
```

---

## Database

- **Engine:** PostgreSQL 15+ with `asyncpg` async driver
- **ORM:** SQLAlchemy 2.x with async sessions
- **Migrations:** Alembic (5 migration files, 0001–0005)
- **Main table:** `medicines` — ~90 Indian branded/generic medicines

### Key migration sequence

| Version | Change |
|---|---|
| `0001` | Create medicines table (core fields) |
| `0002` | Add safety fields (warnings, adverse reactions, precautions) |
| `0003` | Add OpenFDA fields (indications, purpose, allergy warnings) |
| `0004` | Add search indexes (GIN for full-text, btree for salt/dosage) |
| `0005` | Add hybrid search fields (normalized name, FDA sync timestamps) |

---

## Configuration reference

All settings are loaded from `backend/.env` via Pydantic Settings.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | Active LLM backend |
| `LLM_MODEL` | `mock-model` | Model name passed to the provider |
| `DATABASE_URL` | postgres://localhost/medicine_db | Async DB connection string |
| `OPENROUTER_API_KEY` | — | Required for OpenRouter |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `GEMINI_API_KEY` | — | Required for Gemini |
| `GROQ_API_KEY` | — | Required for Groq |
| `AZURE_OPENAI_API_KEY` | — | Required for Azure (also supports vision) |
| `OPENFDA_API_KEY` | — | Optional — increases OpenFDA rate limit |
| `API_V1_PREFIX` | `/api/v1` | URL prefix for all routes |
| `CORS_ORIGINS` | `["*"]` | Allowed frontend origins |

---

## Frontend Architecture

The frontend is a single-file React SPA (`frontend/src/App.jsx`) with no external router — navigation is hash-based.

| Hash | View |
|---|---|
| _(empty)_ | `SearchView` — medicine search + device dropdown |
| `#vendor` | `VendorView` — medicine expiry/discount dashboard |
| `#vendor-devices` | `VendorDevicesView` — device feedback analyser |
| _(selectedDevice state)_ | `DeviceDetailView` — device detail (user-facing) |
| _(result state)_ | `ResultsView` — medicine alternatives |
| _(prescriptionResult state)_ | `PrescriptionResults` — parsed prescription |

All API calls are inline `fetch()` calls — no HTTP client library. Styling is pure CSS in `frontend/src/styles.css` — no component library or Tailwind.
