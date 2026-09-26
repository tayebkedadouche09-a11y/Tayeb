import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Tayeb Integration Gateway", version="0.1.0")

BIM_URL = os.getenv("TAYEB_BIM_URL", "").rstrip("/")


class BIMJob(BaseModel):
    project_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "tayeb-integration-gateway", "bim_configured": bool(BIM_URL)}


@app.get("/api/v1/config")
async def config() -> dict[str, Any]:
    return {"bim_configured": bool(BIM_URL)}


@app.post("/api/v1/bim/jobs")
async def create_bim_job(job: BIMJob) -> dict[str, Any]:
    if not BIM_URL:
        raise HTTPException(status_code=503, detail="TAYEB_BIM_URL is not configured")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{BIM_URL}/api/v1/jobs", json=job.model_dump())
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"BIM service error: {exc}") from exc
