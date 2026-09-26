import json,os,urllib.request
from fastapi import APIRouter,HTTPException,Request
from .db import connect
from .models import *
from .auth import create_password,verify_password,issue_token,require_permission

router=APIRouter()
def rows(sql,args=()):
 with connect() as c:return [dict(x) for x in c.execute(sql,args).fetchall()]
def one(sql,args=()):
 with connect() as c:
  x=c.execute(sql,args).fetchone();return dict(x) if x else None
def audit(a,e,i):
 with connect() as c:c.execute("INSERT INTO audit_log(action,entity,entity_id) VALUES(?,?,?)",(a,e,i))
def insert(table,fields,values):
 try:
  with connect() as c:
   cur=c.execute(f"INSERT INTO {table}({','.join(fields)}) VALUES({','.join('?'*len(values))})",values);i=cur.lastrowid
  audit("create",table,i);return one(f"SELECT * FROM {table} WHERE id=?",(i,))
 except Exception as e: raise HTTPException(409,str(e))
@router.post("/auth/login")
def login(x:LoginIn):
 u=one("SELECT * FROM users WHERE username=? AND active=1",(x.username,))
 if not u or not verify_password(x.password,u["password_hash"]): raise HTTPException(401,"Invalid credentials")
 return {"access_token":issue_token(str(u["id"]),u["role"]),"token_type":"bearer","expires_in":43200,"user":{"id":u["id"],"username":u["username"],"role":u["role"]}}
@router.get("/auth/me")
def me(request:Request):
 return require_permission(request,"projects") | {"ok":True}
@router.get("/auth/users")
def users(request:Request):
 user=require_permission(request,"*")
 if user["role"] not in {"owner","admin"}: raise HTTPException(403,"Admin access required")
 return rows("SELECT id,username,role,active,created_at FROM users ORDER BY id")
@router.post("/auth/users")
def create_user(x:UserIn,request:Request):
 user=require_permission(request,"*")
 if user["role"] not in {"owner","admin"}: raise HTTPException(403,"Admin access required")
 if x.role not in {"owner","admin","project_manager","engineer","accountant","site_manager","viewer"}: raise HTTPException(422,"Invalid role")
 return insert("users",["username","password_hash","role"],[x.username,create_password(x.password),x.role])
@router.get("/dashboard")
def dashboard():
 p=rows("SELECT * FROM projects")
 billed=one("SELECT COALESCE(SUM(gross_amount),0)v FROM billings")["v"]
 income=one("SELECT COALESCE(SUM(amount),0)v FROM cashflow WHERE direction='IN'")["v"]
 out=one("SELECT COALESCE(SUM(amount),0)v FROM cashflow WHERE direction='OUT'")["v"]
 purchases=one("SELECT COALESCE(SUM(amount),0)v FROM purchases")["v"]
 return {"projects":len(p),"active":sum(x["status"]!="Closed" for x in p),"contract_value":sum(x["contract_value"] for x in p),"boq_value":one("SELECT COALESCE(SUM(quantity*unit_rate),0)v FROM boq")["v"],"billed":billed,"cash_in":income,"cash_out":out,"purchases":purchases,"gross_margin_proxy":sum(x["contract_value"] for x in p)-purchases-out}
@router.get("/projects")
def projects():return rows("SELECT * FROM projects ORDER BY id DESC")
@router.post("/projects")
def project(x:ProjectIn):return insert("projects",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/projects/{pid}")
def project_detail(pid:int):
 p=one("SELECT * FROM projects WHERE id=?",(pid,))
 if not p:raise HTTPException(404,"Project not found")
 queries={"tasks":"SELECT * FROM tasks WHERE project_id=?","boq":"SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=?","reports":"SELECT * FROM daily_reports WHERE project_id=? ORDER BY report_date DESC","billings":"SELECT * FROM billings WHERE project_id=?","purchases":"SELECT * FROM purchases WHERE project_id=?","subcontractors":"SELECT * FROM subcontractors WHERE project_id=?","cashflow":"SELECT * FROM cashflow WHERE project_id=? ORDER BY entry_date DESC","attendance":"SELECT a.*,w.name worker_name,w.role FROM attendance a JOIN workers w ON w.id=a.worker_id WHERE a.project_id=? ORDER BY work_date DESC","equipment_logs":"SELECT e.name,e.code,l.* FROM equipment_logs l JOIN equipment e ON e.id=l.equipment_id WHERE l.project_id=? ORDER BY work_date DESC"}
 for k,q in queries.items():p[k]=rows(q,(pid,))
 return p
@router.post("/tasks")
def task(x:TaskIn):
 if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)):raise HTTPException(404,"Project not found")
 return insert("tasks",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/boq")
def boq(project_id:int|None=None):return rows("SELECT *,quantity*unit_rate amount FROM boq WHERE project_id=COALESCE(?,project_id) ORDER BY project_id,code",(project_id,))
@router.post("/boq")
def add_boq(x:BOQIn):return insert("boq",list(x.model_dump().keys()),list(x.model_dump().values()))
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
@router.post("/equipment/logs")
def equipment_log(x:EquipmentLogIn):
 e=one("SELECT hourly_rate FROM equipment WHERE id=?",(x.equipment_id,))
 if not e:raise HTTPException(404,"Equipment not found")
 return insert("equipment_logs",["equipment_id","project_id","work_date","hours","cost","notes"],[x.equipment_id,x.project_id,x.work_date,x.hours,x.hours*e["hourly_rate"],x.notes])
@router.get("/materials")
def materials():return rows("SELECT *,stock*unit_cost stock_value,CASE WHEN stock<=reorder_level THEN 1 ELSE 0 END low_stock FROM materials")
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
 audit("stock_move","material",x.material_id);return one("SELECT * FROM material_moves WHERE id=?",(i,))
@router.get("/purchases")
def purchases(project_id:int|None=None):return rows("SELECT * FROM purchases WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC",(project_id,))
@router.post("/purchases")
def purchase(x:PurchaseIn):return insert("purchases",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/purchases/{purchase_id}/items")
def purchase_item(purchase_id:int,x:PurchaseItemIn):
 if not one("SELECT id FROM purchases WHERE id=?",(purchase_id,)): raise HTTPException(404,"Purchase not found")
 if x.material_id is not None and not one("SELECT id FROM materials WHERE id=?",(x.material_id,)): raise HTTPException(404,"Material not found")
 return insert("purchase_items",["purchase_id","material_id","description","quantity","unit_rate"],[purchase_id,x.material_id,x.description,x.quantity,x.unit_rate])
@router.get("/purchases/{purchase_id}")
def purchase_detail(purchase_id:int):
 p=one("SELECT * FROM purchases WHERE id=?",(purchase_id,))
 if not p: raise HTTPException(404,"Purchase not found")
 p["items"]=rows("SELECT pi.*,m.code material_code,m.name material_name,pi.quantity*pi.unit_rate amount FROM purchase_items pi LEFT JOIN materials m ON m.id=pi.material_id WHERE pi.purchase_id=?",(purchase_id,))
 p["items_total"]=sum(x["amount"] for x in p["items"])
 return p
@router.post("/purchases/{purchase_id}/receive")
def receive_purchase(purchase_id:int):
 p=one("SELECT * FROM purchases WHERE id=?",(purchase_id,))
 if not p: raise HTTPException(404,"Purchase not found")
 if p["status"]=="Received": raise HTTPException(409,"Purchase already received")
 items=rows("SELECT * FROM purchase_items WHERE purchase_id=?",(purchase_id,))
 with connect() as c:
  for item in items:
   if item["material_id"] is not None:
    c.execute("UPDATE materials SET stock=stock+? WHERE id=?",(item["quantity"],item["material_id"]))
    c.execute("INSERT INTO material_moves(project_id,material_id,quantity,move_type,reference) VALUES(?,?,?,?,?)",(p["project_id"],item["material_id"],item["quantity"],"RECEIPT",p["reference"]))
  c.execute("UPDATE purchases SET status='Received' WHERE id=?",(purchase_id,))
 audit("receive","purchase",purchase_id)
 return one("SELECT * FROM purchases WHERE id=?",(purchase_id,))
@router.get("/subcontractors")
def subcontractors(project_id:int|None=None):return rows("SELECT * FROM subcontractors WHERE project_id=COALESCE(?,project_id)",(project_id,))
@router.post("/subcontractors")
def subcontractor(x:SubcontractIn):return insert("subcontractors",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/daily-reports")
def daily(x:DailyReportIn):return insert("daily_reports",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.post("/billings")
def billing(x:BillingIn):
 d=x.model_dump();i=insert("billings",list(d.keys()),list(d.values()));i["retention_amount"]=x.gross_amount*x.retention_percent/100;i["net_amount"]=x.gross_amount-i["retention_amount"]+x.tax_amount;return i
@router.get("/billings")
def billings(project_id:int|None=None):return rows("SELECT *,gross_amount*retention_percent/100 retention_amount,gross_amount-gross_amount*retention_percent/100+tax_amount net_amount FROM billings WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC",(project_id,))
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
   with urllib.request.urlopen(req,timeout=15) as r:result=json.loads(r.read())
   with connect() as c:c.execute("UPDATE bim_jobs SET status='Submitted',result_json=? WHERE id=?",(json.dumps(result),i["id"]))
  except Exception as e:
   with connect() as c:c.execute("UPDATE bim_jobs SET status='GatewayError',result_json=? WHERE id=?",(json.dumps({"error":str(e)}),i["id"]))
 return one("SELECT * FROM bim_jobs WHERE id=?",(i["id"],))
@router.post("/costs")
def cost(x:CostIn): return insert("cost_entries",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/costs")
def costs(project_id:int|None=None): return rows("SELECT * FROM cost_entries WHERE project_id=COALESCE(?,project_id) ORDER BY entry_date DESC",(project_id,))
@router.get("/projects/{pid}/financial-summary")
def financial_summary(pid:int):
 if not one("SELECT id FROM projects WHERE id=?",(pid,)): raise HTTPException(404,"Project not found")
 contract=one("SELECT contract_value v FROM projects WHERE id=?",(pid,))["v"]
 boq=one("SELECT COALESCE(SUM(quantity*unit_rate),0)v FROM boq WHERE project_id=?",(pid,))["v"]
 billed=one("SELECT COALESCE(SUM(gross_amount),0)v FROM billings WHERE project_id=?",(pid,))["v"]
 cash_in=one("SELECT COALESCE(SUM(amount),0)v FROM cashflow WHERE project_id=? AND direction='IN'",(pid,))["v"]
 cash_out=one("SELECT COALESCE(SUM(amount),0)v FROM cashflow WHERE project_id=? AND direction='OUT'",(pid,))["v"]
 costs_total=one("SELECT COALESCE(SUM(amount),0)v FROM cost_entries WHERE project_id=?",(pid,))["v"]
 purchases=one("SELECT COALESCE(SUM(amount),0)v FROM purchases WHERE project_id=?",(pid,))["v"]
 equipment=one("SELECT COALESCE(SUM(cost),0)v FROM equipment_logs WHERE project_id=?",(pid,))["v"]
 return {"contract_value":contract,"boq_value":boq,"billed":billed,"cash_in":cash_in,"cash_out":cash_out,"direct_costs":costs_total,"purchases":purchases,"equipment_cost":equipment,"estimated_cost":costs_total+purchases+equipment,"remaining_contract":contract-billed}
@router.get("/audit")
def audit_log():return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500")
@router.get("/health/modules")
def module_health():return {"projects":True,"boq":True,"labour":True,"equipment":True,"materials":True,"procurement":True,"subcontractors":True,"site_reports":True,"billing":True,"cashflow":True,"bim_boundary":True}