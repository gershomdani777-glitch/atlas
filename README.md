# ATLAS

ATLAS is an autonomous paper-trading agent built for CSI ORIGIN 2026, Problem Statement 3. It runs a continuous
perceive → interpret → classify-regime → allocate/risk-check → execute → observe-outcome → adapt loop as an
explicit LangGraph state graph, against live Binance market data, with Gemini proposing trade theses that a
deterministic risk engine alone can accept, reject, or resize.

## Architecture

- **`backend/`** — FastAPI + LangGraph (Python). The real system: live Binance ingestion, Gemini-based interpretation,
  Postgres+pgvector persistence and outcome-conditioned memory, and the `/ws/live` stream.
- **`frontend/`** — Next.js operator dashboard (Live Ops, Decision Feed, Decision Receipt, Performance, Risk Console).
- **`server.js` / `public/`** — an earlier zero-dependency Node.js prototype, kept only as a static fallback demo. It
  is not connected to the real backend and is not being extended further.

## Running locally

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your Supabase DATABASE_URL, Upstash REDIS_URL, GOOGLE_API_KEY
python -m db.init_db    # one-time: creates the pgvector extension, tables, seeds assets + default risk config
uvicorn main:app --reload
```

Runs the ingestion loop, the 7-stage agent loop, and the API + `/ws/live` WebSocket together.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # point at your backend's URL if not localhost:8000
npm run dev
```

Open http://localhost:3000.

### Tests

```bash
cd backend
pytest -v
```

Covers the regime classifier, the risk/allocation engine's constraint checks, and a full 7-node graph cycle
(mocked LLM call, real persistence against an in-memory SQLite DB).

## Deployment

- Backend → Render (`render.yaml` at repo root), free tier. A GitHub Actions workflow
  (`.github/workflows/keep-alive.yml`) pings it every 10 minutes to reduce cold starts — add a
  `RENDER_BACKEND_URL` repo secret pointing at your deployed backend's base URL to enable it.
- Frontend → Vercel, with **Root Directory** set to `frontend` in the project settings, and
  `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` pointed at the deployed backend.

## Core design

The LLM (Gemini) only ever *proposes* a structured thesis — it never sizes or executes. A deterministic risk engine
(cost-adjusted edge filter, fractional-Kelly sizing, regime-throttle multipliers, hard exposure/drawdown caps)
is the sole path by which a thesis becomes a simulated order. Every decision — accepted or rejected — is persisted
with its full input snapshot, constraint checks, and sizing math for the Decision Receipt view.
