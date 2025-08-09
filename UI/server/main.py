from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import List, Literal, TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# Configuration
PORT = int(os.getenv("PORT", "8000"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class Row(BaseModel):
    order_id: str
    date_ordered: str
    product_type: str
    customer_type: str
    price: str
    competitor_price: str
    promotion_flag: str
    marketing_spend: str
    economic_index: str
    seasonality_index: str
    trend_index: str
    day_of_week: str
    month: str
    price_gap: str
    quantity: str


class UploadPayload(BaseModel):
    rows: List[Row] = Field(default_factory=list)


class RetrainResponse(BaseModel):
    job_id: str
    message: str


app = FastAPI(title="Smart Pricing Service (Placeholder)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/api/pricing/upload")
def upload_training_data(payload: UploadPayload):
    if not payload.rows:
        raise HTTPException(status_code=400, detail="No rows provided")

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_path = UPLOADS_DIR / f"training-data-{timestamp}.json"
    with file_path.open("w", encoding="utf-8") as f:
        json.dump({"rows": [r.model_dump() for r in payload.rows]}, f)

    return {
        "message": "Data received",
        "saved_to": str(file_path),
        "num_rows": len(payload.rows),
    }


@app.post("/api/pricing/retrain", response_model=RetrainResponse)
def retrain_model():
    # In a real implementation, enqueue a background job or trigger your pipeline here
    job_id = uuid.uuid4().hex[:12]
    return RetrainResponse(job_id=job_id, message="Retraining started. This may take several minutes.")


@app.get("/api/pricing/recommendations")
def recommendations():
    # Placeholder; replace with your model's outputs
    return [
        {"sku": "AB-HEPES-1KG", "currentPrice": 185, "recommendedPrice": 199, "liftPct": 7.6},
        {"sku": "TF-PIPET-200", "currentPrice": 29, "recommendedPrice": 27, "liftPct": -6.9},
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)

