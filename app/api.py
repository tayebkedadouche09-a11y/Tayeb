import json, os, urllib.request
from fastapi import APIRouter, HTTPException
from .db import connect
from .models import *
router=APIRouter()

def rows(sql,args=()):
    with connect() as c: return [dict(x) for x in c.execute(sql,args).fetchall()]
def one(sql,args=()):
    with connect() as c:
        r=c.execute(sql,args).fetchone()
        return dict(r) if r else None
def audit(action,entity,eid):
    with connect() as c: c.execute("INSERT INTO audit_log(action,entity,entity_id) VALUES(?,?,?)",(action,entity,eid))

@router.get("/dashboard")
def dashboard():
    p=rows("SELECT * FROM projects ORDER BY id DESC")
    total=sum(x["contract_value"] for x in p)
    return {"projects":len(p),"contract_value":total,"active":sum(x["status"]!="Closed" for x in p),
            "boq_value":one("SELECT COALESCE(SUM(quantity*unit_rate),0) v FROM boq")["v"],
            "billed":one("SELECT COALESCE(SUM(gross_amount),0) v FROM billings")["v"]}

@router.get("/projects")
def projects(): return rows("SELECT * FROM projects ORDER BY id DESC")

@router.post("/projects")
def create_project(x:ProjectIn):
    try:
        with connect() as c:
            cur=c.execute("INSERT INTO projects(code,name,client,location,contract_value,start_date,end_date) VALUES(?,?,?,?,?,?,?)",
              (x.code,x.name,x.client,x.location,x.contract_value,x.start_date,x.end_date))
            i=cur.lastrowid
        audit("create","project",i); return one("SELECT * FROM projects WHERE id=?",(i,))
    except Exception as e: raise HTTPException(409,str(e))

@router.get("/projects/{pid}")
def project(pid:int):
    p=one("SELECT * FROM projects WHERE id=?",(pid,))
    if not p: raise HTTPException(404,"Project not found")
    p["tasks"]=rows("SELECT * FROM tasks WHERE project_id=?",(pid,))
    p["boq"]=rows("SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=?",(pid,))
    p["reports"]=rows("SELECT * FROM daily_reports WHERE project_id=? ORDER BY report_date DESC",(pid,))
    p["billings"]=rows("SELECT * FROM billings WHERE project_id=? ORDER BY id DESC",(pid,))
    return p

@router.post("/tasks")
def task(x:TaskIn):
    with connect() as c:
        i=c.execute("INSERT INTO tasks(project_id,name,start_date,end_date,progress) VALUES(?,?,?,?,?)",
          (x.project_id,x.name,x.start_date,x.end_date,x.progress)).lastrowid
    audit("create","task",i); return one("SELECT * FROM tasks WHERE id=?",(i,))

@router.get("/boq")
def boq(project_id:int|None=None):
    return rows("SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=COALESCE(?,project_id) ORDER BY project_id,code",(project_id,))

@router.post("/boq")
def add_boq(x:BOQIn):
    with connect() as c:
        i=c.execute("INSERT INTO boq(project_id,code,description,unit,quantity,unit_rate,category) VALUES(?,?,?,?,?,?,?)",
          (x.project_id,x.code,x.description,x.unit,x.quantity,x.unit_rate,x.category)).lastrowid
    audit("create","boq",i); return one("SELECT *,quantity*unit_rate amount FROM boq WHERE id=?",(i,))

@router.get("/resources")
def resources(kind:str|None=None): return rows("SELECT * FROM resources WHERE kind=COALESCE(?,kind)",(kind,))

@router.post("/resources")
def add_resource(x:ResourceIn):
    with connect() as c:
        i=c.execute("INSERT INTO resources(kind,code,name,unit,unit_cost) VALUES(?,?,?,?,?)",
          (x.kind,x.code,x.name,x.unit,x.unit_cost)).lastrowid
    return one("SELECT * FROM resources WHERE id=?",(i,))

@router.post("/daily-reports")
def daily(x:DailyReportIn):
    with connect() as c:
        i=c.execute("INSERT INTO daily_reports(project_id,report_date,summary,progress_percent,labour_count,material_cost,equipment_cost,notes) VALUES(?,?,?,?,?,?,?,?)",
          (x.project_id,x.report_date,x.summary,x.progress_percent,x.labour_count,x.material_cost,x.equipment_cost,x.notes)).lastrowid
    return one("SELECT * FROM daily_reports WHERE id=?",(i,))

@router.post("/billings")
def billing(x:BillingIn):
    net=x.gross_amount-(x.gross_amount*x.retention_percent/100)+x.tax_amount
    with connect() as c:
        i=c.execute("INSERT INTO billings(project_id,invoice_no,gross_amount,retention_percent,tax_amount) VALUES(?,?,?,?,?)",
          (x.project_id,x.invoice_no,x.gross_amount,x.retention_percent,x.tax_amount)).lastrowid
    return {"id":i,"net_amount":net,"status":"Draft"}

@router.post("/bim/jobs")
def bim(x:BIMJobIn):
    with connect() as c:
        i=c.execute("INSERT INTO bim_jobs(project_id,source_type,source_uri,job_type) VALUES(?,?,?,?)",
          (x.project_id,x.source_type,x.source_uri,x.job_type)).lastrowid
    target=os.getenv("TAYEB_BIM_URL","").rstrip("/")
    if target:
        try:
            req=urllib.request.Request(target+"/api/v1/jobs",data=json.dumps(x.model_dump()).encode(),headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req,timeout=10) as r: result=json.loads(r.read())
            with connect() as c: c.execute("UPDATE bim_jobs SET status='Submitted',result_json=? WHERE id=?",(json.dumps(result),i))
        except Exception as e:
            with connect() as c: c.execute("UPDATE bim_jobs SET status='GatewayError',result_json=? WHERE id=?",(json.dumps({"error":str(e)}),i))
    return one("SELECT * FROM bim_jobs WHERE id=?",(i,))

@router.get("/audit")
def audit_log(): return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200")
