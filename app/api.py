import json,os,urllib.request
from fastapi import APIRouter,HTTPException
from .db import connect
from .models import *
router=APIRouter()
def rows(sql,args=()):
 with connect() as c:return [dict(x) for x in c.execute(sql,args).fetchall()]
def one(sql,args=()):
 with connect() as c:
  x=c.execute(sql,args).fetchone(); return dict(x) if x else None
def audit(a,e,i):
 with connect() as c:c.execute("INSERT INTO audit_log(action,entity,entity_id) VALUES(?,?,?)",(a,e,i))
def insert(table,fields,values):
 with connect() as c:
  cur=c.execute(f"INSERT INTO {table}({','.join(fields)}) VALUES({','.join('?'*len(values))})",values); i=cur.lastrowid
 audit("create",table,i); return one(f"SELECT * FROM {table} WHERE id=?",(i,))
@router.get("/dashboard")
def dashboard():
 p=rows("SELECT * FROM projects"); billed=one("SELECT COALESCE(SUM(gross_amount),0)v FROM billings")["v"]
 cost=one("""SELECT COALESCE((SELECT SUM(amount) FROM purchases)+(SELECT SUM(amount) FROM cashflow WHERE direction='OUT'),0)v""")["v"]
 return {"projects":len(p),"active":sum(x["status"]!="Closed" for x in p),"contract_value":sum(x["contract_value"] for x in p),"boq_value":one("SELECT COALESCE(SUM(quantity*unit_rate),0)v FROM boq")["v"],"billed":billed,"recorded_cost":cost}
@router.get("/projects")
def projects():return rows("SELECT * FROM projects ORDER BY id DESC")
@router.post("/projects")
def project(x:ProjectIn):
 try:return insert("projects",["code","name","client","location","contract_value","start_date","end_date"],[x.code,x.name,x.client,x.location,x.contract_value,x.start_date,x.end_date])
 except Exception as e:raise HTTPException(409,str(e))
@router.get("/projects/{pid}")
def project_detail(pid:int):
 p=one("SELECT * FROM projects WHERE id=?",(pid,))
 if not p:raise HTTPException(404,"Project not found")
 for key,sql in {"tasks":"SELECT * FROM tasks WHERE project_id=?","boq":"SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=?","reports":"SELECT * FROM daily_reports WHERE project_id=? ORDER BY report_date DESC","billings":"SELECT * FROM billings WHERE project_id=?","purchases":"SELECT * FROM purchases WHERE project_id=?","subcontractors":"SELECT * FROM subcontractors WHERE project_id=?","cashflow":"SELECT * FROM cashflow WHERE project_id=? ORDER BY entry_date DESC"}.items():p[key]=rows(sql,(pid,))
 return p
@router.post("/tasks")
def task(x:TaskIn):return insert("tasks",["project_id","name","start_date","end_date","progress"],x.model_dump().values())
@router.get("/boq")
def boq(project_id:int|None=None):return rows("SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=COALESCE(?,project_id) ORDER BY project_id,code",(project_id,))
@router.post("/boq")
def add_boq(x:BOQIn):return insert("boq",["project_id","code","description","unit","quantity","unit_rate","category"],list(x.model_dump().values()))
@router.get("/workers")
def workers():return rows("SELECT * FROM workers WHERE active=1")
@router.post("/workers")
def worker(x:WorkerIn):return insert("workers",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/attendance")
def attendance(x:AttendanceIn):return insert("attendance",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/attendance")
def attendance_list(project_id:int|None=None):return rows("SELECT a.*,w.name worker_name,w.role FROM attendance a JOIN workers w ON w.id=a.worker_id WHERE a.project_id=COALESCE(?,a.project_id) ORDER BY work_date DESC",(project_id,))
@router.get("/equipment")
def equipment():return rows("SELECT * FROM equipment")
@router.post("/equipment")
def equipment_add(x:EquipmentIn):return insert("equipment",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/materials")
def materials():return rows("SELECT * FROM materials")
@router.post("/materials")
def material(x:MaterialIn):return insert("materials",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/materials/move")
def material_move(x:MaterialMoveIn):
 with connect() as c:
  m=c.execute("SELECT stock FROM materials WHERE id=?",(x.material_id,)).fetchone()
  if not m:raise HTTPException(404,"Material not found")
  delta=-x.quantity if x.move_type.upper() in {"CONSUMPTION","ISSUE","TRANSFER_OUT"} else x.quantity
  if m["stock"]+delta<0:raise HTTPException(409,"Insufficient stock")
  c.execute("UPDATE materials SET stock=stock+? WHERE id=?",(delta,x.material_id))
  i=c.execute("INSERT INTO material_moves(project_id,material_id,quantity,move_type,reference) VALUES(?,?,?,?,?)",(x.project_id,x.material_id,x.quantity,x.move_type,x.reference)).lastrowid
 return one("SELECT * FROM material_moves WHERE id=?",(i,))
@router.post("/purchases")
def purchase(x:PurchaseIn):return insert("purchases",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/subcontractors")
def subcontractor(x:SubcontractIn):return insert("subcontractors",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/daily-reports")
def daily(x:DailyReportIn):return insert("daily_reports",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/billings")
def billing(x:BillingIn):
 d=x.model_dump(); i=insert("billings",list(d.keys()),list(d.values())); i["net_amount"]=x.gross_amount-x.gross_amount*x.retention_percent/100+x.tax_amount; return i
@router.post("/cashflow")
def cashflow(x:CashflowIn):return insert("cashflow",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/cashflow")
def cashflow_list(project_id:int|None=None):return rows("SELECT * FROM cashflow WHERE project_id=COALESCE(?,project_id) ORDER BY entry_date DESC",(project_id,))
@router.post("/bim/jobs")
def bim(x:BIMJobIn):
 i=insert("bim_jobs",["project_id","source_type","source_uri","job_type"],list(x.model_dump().values()))
 target=os.getenv("TAYEB_BIM_URL","").rstrip("/")
 if target:
  try:
   req=urllib.request.Request(target+"/api/v1/jobs",data=json.dumps(x.model_dump()).encode(),headers={"Content-Type":"application/json"})
   with urllib.request.urlopen(req,timeout=10) as r:result=json.loads(r.read())
   with connect() as c:c.execute("UPDATE bim_jobs SET status='Submitted',result_json=? WHERE id=?",(json.dumps(result),i["id"]))
  except Exception as e:
   with connect() as c:c.execute("UPDATE bim_jobs SET status='GatewayError',result_json=? WHERE id=?",(json.dumps({"error":str(e)}),i["id"]))
 return one("SELECT * FROM bim_jobs WHERE id=?",(i["id"],))
@router.get("/audit")
def audit_log():return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500")
@router.get("/health/modules")
def module_health():
 return {"projects":True,"boq":True,"labour":True,"equipment":True,"materials":True,"procurement":True,"subcontractors":True,"site_reports":True,"billing":True,"cashflow":True,"bim_boundary":True}