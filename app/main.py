from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
from .db import init_db
from .api import router

app = FastAPI(title="Tayeb Construction ERP", version="0.1.0")
app.include_router(router, prefix="/api")

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status":"ok","service":"tayeb-erp"}

@app.get("/", response_class=HTMLResponse)
def home():
    return Path(__file__).with_name("web").joinpath("index.html").read_text(encoding="utf-8")
