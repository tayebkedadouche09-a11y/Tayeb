import os
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse
from pathlib import Path
from .db import init_db
from .api import router

app=FastAPI(title="Tayeb Construction ERP",version="1.0.0",docs_url="/docs",redoc_url="/redoc")
app.include_router(router,prefix="/api")

@app.middleware("http")
async def api_guard(request:Request,call_next):
    token=os.getenv("TAYEB_API_TOKEN","").strip()
    if token and request.url.path.startswith("/api") and request.url.path not in {"/api/health","/api/health/modules"}:
        supplied=request.headers.get("authorization","")
        if supplied!=f"Bearer {token}":
            return JSONResponse({"detail":"Authentication required"},status_code=401)
    return await call_next(request)

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health(): return {"status":"ok","service":"tayeb-erp","version":"1.0.0"}

@app.get("/",response_class=HTMLResponse)
def home(): return Path(__file__).with_name("web").joinpath("index.html").read_text(encoding="utf-8")
