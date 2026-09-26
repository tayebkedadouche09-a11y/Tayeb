import os
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse,JSONResponse
from pathlib import Path
from .db import init_db
from .api import router
from .auth import bootstrap_owner,current_user,PERMISSIONS

app=FastAPI(title="Tayeb Construction ERP",version="1.2.0",docs_url="/docs",redoc_url="/redoc")
app.include_router(router,prefix="/api")
PUBLIC={"/api/auth/login","/api/health","/api/health/modules"}
PERM_BY_PATH={
 "/api/projects":"projects","/api/boq":"boq","/api/tasks":"tasks","/api/workers":"workers","/api/attendance":"attendance",
 "/api/equipment":"equipment","/api/materials":"materials","/api/purchases":"purchases","/api/subcontractors":"subcontractors",
 "/api/daily-reports":"reports","/api/billings":"billings","/api/cashflow":"cashflow","/api/costs":"costs","/api/bim/jobs":"bim",
 "/api/dashboard":"projects","/api/audit":"projects","/api/payroll":"payroll","/api/change-orders":"projects","/api/progress":"boq","/api/billing-payments":"billings","/api/documents":"projects","/api/issues":"projects","/api/accounting":"accounting","/api/budgets":"projects"
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
            else:
                user=current_user(request)
                if user is None:
                    return JSONResponse({"detail":"Authentication required"},status_code=401)
            perm=next((v for k,v in PERM_BY_PATH.items() if path==k or path.startswith(k+"/")),None)
            if perm is None and user["role"] not in {"owner","admin"} and not path.startswith("/api/auth/"):
                return JSONResponse({"detail":"Permission denied"},status_code=403)
            if perm and user["role"] not in {"owner","admin"} and perm not in PERMISSIONS.get(user["role"],set()):
                return JSONResponse({"detail":"Permission denied"},status_code=403)
        if auth_enabled:
            qpid=request.query_params.get("project_id")
                if not qpid and request.method in {"POST","PUT","PATCH"}:
                    try:
                        import json
                        body=await request.body()
                        if body:
                            payload=json.loads(body)
                            if isinstance(payload,dict) and payload.get("project_id") is not None:
                                qpid=str(payload["project_id"])
                    except Exception:
                        pass
                if not qpid and user.get("role") not in {"owner","admin","legacy"}:
                    from .db import connect
                    import re
                    m=re.match(r"^/api/(purchases|billings|documents|issues|change-orders|billing-payments|supplier-invoices|supplier-payments)/(\d+)",path)
                    if m:
                        table,rid=m.group(1),int(m.group(2))
                        try:
                            with connect() as db:
                                if table=="billing-payments":
                                    row=db.execute("SELECT b.project_id FROM billing_payments bp JOIN billings b ON b.id=bp.billing_id WHERE bp.id=?",(rid,)).fetchone()
                                elif table=="supplier-payments":
                                    row=db.execute("SELECT si.project_id FROM supplier_payments sp JOIN supplier_invoices si ON si.id=sp.supplier_invoice_id WHERE sp.id=?",(rid,)).fetchone()
                                else:
                                    row=db.execute("SELECT project_id FROM "+table.replace("-","_")+" WHERE id=?",(rid,)).fetchone()
                            if row and row["project_id"] is not None: qpid=str(row["project_id"])
                        except Exception:
                            pass
                if qpid and user.get("role") not in {"owner","admin","legacy"}:
                    try:
                        from .db import connect
                        pid=int(qpid)
                        with connect() as db:
                            if not db.execute("SELECT 1 FROM projects WHERE id=?",(pid,)).fetchone(): return JSONResponse({"detail":"Project not found"},status_code=404)
                            if not db.execute("SELECT 1 FROM project_members WHERE project_id=? AND user_id=?",(pid,int(user["sub"]))).fetchone(): return JSONResponse({"detail":"Project access denied"},status_code=403)
                    except ValueError: return JSONResponse({"detail":"Invalid project_id"},status_code=422)
                return await call_next(request)

@app.on_event("startup")
def startup():
    init_db()
    bootstrap_owner()
@app.get("/health")
def health(): return {"status":"ok","service":"tayeb-erp","version":"1.1.0"}
@app.get("/",response_class=HTMLResponse)
def home(): return Path(__file__).with_name("web").joinpath("index.html").read_text(encoding="utf-8")