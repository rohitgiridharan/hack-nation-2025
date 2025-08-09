# Smart Pricing AI – UI & Pricing Service (Placeholder)

## UI (React + Vite)

Install dependencies and run the development server:

```
npm install
npm run dev
```

Environment variables used by the UI:

```
VITE_PRICING_UPLOAD_URL=http://localhost:8000/api/pricing/upload
VITE_PRICING_RETRAIN_URL=http://localhost:8000/api/pricing/retrain
```

## Pricing Service (FastAPI placeholder)

A minimal FastAPI service is included under `server/` for local testing. It exposes:
- `POST /api/pricing/upload` – accept training rows (JSON) saved to disk.
- `POST /api/pricing/retrain` – trigger a placeholder retrain job and return a job id.
- `GET /api/pricing/recommendations` – sample recommendations data.

### Run locally

```
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then in another terminal, start the UI:

```
export VITE_PRICING_UPLOAD_URL=http://localhost:8000/api/pricing/upload
export VITE_PRICING_RETRAIN_URL=http://localhost:8000/api/pricing/retrain
npm run dev
```
