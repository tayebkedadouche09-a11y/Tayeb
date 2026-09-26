import os
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse
from pathlib import Path
from .db import init_db
from .api import router
from .auth import bootstrap_owner,verify_token,PERMISSIONS

app=FastAPI(title="Tayeb Construction ERP",version="1.1.0",docs_url="/docs",redoc_url="/redoc")
app.include_router(router,prefix="/api")
PUBLIC={"/api/auth/login","/api/health","/api/health/modules"}
PERM_BY_PATH={
 "/api/projects":"projects","/api/boq":"boq","/api/tasks":"tasks","/api/workers":"workers","/api/attendance":"attendance",
 "/api/equipment":"equipment","/api/materials":"materials","/api/purchases":"purchases","/api/subcontractors":"subcontractors",
 "/api/daily-reports":"reports","/api/billings":"billings","/api/cashflow":"cashflow","/api/costs":"costs","/api/bim/jobs":"bim",
 "/api/dashboard":"projects","/api/audit":"projects","/api/payroll":"payroll","/api/change-orders":"projects","/api/progress":"boq","/api/billing-payments":"billings","/api/documents":"projects","/api/issues":"projects"
}
@app.middleware("http")
async def api_guard(request:Request,call_next):
    path=request.url.path
    if path.startswith("/api") and path not in PUBLIC:
        supplied=request.headers.get("authorization","")
        legacy=os.getenv("TAYEB_API_TOKEN","").strip()
        auth_enabled=bool(os.getenv("TAYEB_BOOTSTRAP_PASSWORD") or os.getenv("TAYEB_AUTH_SECRET") or legacy)
        if auth_enabled:
            if legacy and supplied==f"Bearer {legacy}":
                user={"sub":"legacy","role":"owner"}
            elif supplied.startswith("Bearer ") and (user:=verify_token(supplied[7:].strip())):
                pass
            else:
                return JSONResponse({"detail":"Authentication required"},status_code=401)
            perm=next((v for k,v in PERM_BY_PATH.items() if path==k or path.startswith(k+"/")),None)
            if perm and user["role"] not in {"owner","admin"} and perm not in PERMISSIONS.get(user["role"],set()):
                return JSONResponse({"detail":"Permission denied"},status_code=403)
    return await call_next(request)
@app.on_event("startup")
def startup():
    init_db()
    bootstrap_owner()
@app.get("/health")
def health(): return {"status":"ok","service":"tayeb-erp","version":"1.1.0"}
@app.get("/",response_class=HTMLResponse)
def home(): return Path(__file__).with_name("web").joinpath("index.html").read_text(encoding="utf-8")