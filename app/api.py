import json,os,urllib.request,hashlib
from fastapi import APIRouter,HTTPException,Request,UploadFile,File
from .db import connect
from .models import *
from .auth import create_password,verify_password,issue_token,require_permission
from pathlib import Path
import uuid

router=APIRouter()
def rows(sql,args=()):
 with connect() as c:return [dict(x) for x in c.execute(sql,args).fetchall()]
def one(sql,args=()):
 with connect() as c:
  x=c.execute(sql,args).fetchone();return dict(x) if x else None
def audit(a,e,i):
 with connect() as c:c.execute("INSERT INTO audit_log(action,entity,entity_id) VALUES(?,?,?)",(a,e,i))
def account_id(code):
    a=one("SELECT id FROM accounts WHERE code=? AND active=1",(code,))
    if not a: raise HTTPException(500,f"Required account {code} is not configured")
    return a["id"]
def post_system_journal(entry_no,entry_date,description,project_id,lines):
    fp=one("SELECT status FROM fiscal_periods WHERE start_date<=? AND end_date>=? ORDER BY id DESC LIMIT 1",(entry_date,entry_date))
    if fp and fp["status"]=="Closed": raise HTTPException(409,"Fiscal period is closed")
    if any(l[1] < 0 or l[2] < 0 or (l[1] and l[2]) for l in lines): raise HTTPException(500,"Invalid system journal line")
    debit=sum(l[1] for l in lines); credit=sum(l[2] for l in lines)
    if abs(debit-credit)>0.000001: raise HTTPException(500,"System journal is not balanced")
    with connect() as c:
        existing=c.execute("SELECT id FROM journal_entries WHERE entry_no=?",(entry_no,)).fetchone()
        if existing: return existing["id"]
        jid=c.execute("INSERT INTO journal_entries(entry_no,entry_date,description,project_id,status,posted_at) VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)",(entry_no,entry_date,description,project_id,"Posted")).lastrowid
        for aid,debit_amt,credit_amt,desc,line_project in lines:
            c.execute("INSERT INTO journal_lines(journal_id,account_id,debit,credit,description,project_id) VALUES(?,?,?,?,?,?)",(jid,aid,debit_amt,credit_amt,desc,line_project))
    audit("post","journal_entry",jid)
    return jid

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
    items_total=sum(x["quantity"]*x["unit_rate"] for x in items)
    amount=p["amount"] or items_total
    if amount<=0: raise HTTPException(422,"Purchase amount must be greater than zero")
    with connect() as c:
        for item in items:
            if item["material_id"] is not None:
                c.execute("UPDATE materials SET stock=stock+? WHERE id=?",(item["quantity"],item["material_id"]))
                c.execute("INSERT INTO material_moves(project_id,material_id,quantity,move_type,reference) VALUES(?,?,?,?,?)",(p["project_id"],item["material_id"],item["quantity"],"RECEIPT",p["reference"]))
        c.execute("UPDATE purchases SET status='Received',amount=? WHERE id=?",(amount,purchase_id))
    post_system_journal("PUR-"+str(purchase_id),p["created_at"][:10] if p["created_at"] else "2099-01-01","Purchase receipt "+p["reference"],p["project_id"],[(account_id("1200"),amount,0,"Inventory receipt",p["project_id"]),(account_id("2000"),0,amount,"Supplier payable",p["project_id"])])
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
 d=x.model_dump(); i=insert("billings",list(d.keys()),list(d.values()))
 retention=x.gross_amount*x.retention_percent/100; net=x.gross_amount-retention+x.tax_amount
 lines=[(account_id("1100"),net,0,"Accounts receivable",x.project_id),(account_id("1300"),retention,0,"Retention receivable",x.project_id),(account_id("4000"),0,x.gross_amount,"Construction revenue",x.project_id)]
 if x.tax_amount: lines.append((account_id("2200"),0,x.tax_amount,"Tax payable",x.project_id))
 post_system_journal("INV-"+str(i["id"]),i["created_at"][:10] if i["created_at"] else "2099-01-01","Invoice "+x.invoice_no,x.project_id,lines)
 i["retention_amount"]=retention; i["net_amount"]=net; return i
@router.get("/billings")
def billings(project_id:int|None=None):return rows("""SELECT *,
                 gross_amount*retention_percent/100 retention_amount,
                 gross_amount-gross_amount*retention_percent/100+tax_amount net_amount,
                 COALESCE((SELECT SUM(bp.amount) FROM billing_payments bp WHERE bp.billing_id=billings.id),0) paid,
                 CASE
                   WHEN COALESCE((SELECT SUM(bp.amount) FROM billing_payments bp WHERE bp.billing_id=billings.id),0) >= gross_amount-gross_amount*retention_percent/100+tax_amount THEN 'Paid'
                   WHEN COALESCE((SELECT SUM(bp.amount) FROM billing_payments bp WHERE bp.billing_id=billings.id),0) > 0 THEN 'Partially Paid'
                   ELSE status
                 END effective_status
                 FROM billings WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC""",(project_id,))
@router.post("/cashflow")
def cashflow(x:CashflowIn):
    if x.direction not in {"IN","OUT"}: raise HTTPException(422,"Direction must be IN or OUT")
    if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)): raise HTTPException(404,"Project not found")
    return insert("cashflow",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/cashflow")
def cashflow_list(project_id:int|None=None):return rows("SELECT * FROM cashflow WHERE project_id=COALESCE(?,project_id) ORDER BY entry_date DESC",(project_id,))
@router.get("/bim/jobs")
def bim_jobs(project_id:int|None=None):
 return rows("SELECT * FROM bim_jobs WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC",(project_id,))
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
 labour=one("SELECT COALESCE(SUM(a.hours*w.daily_rate/8),0)v FROM attendance a JOIN workers w ON w.id=a.worker_id WHERE a.project_id=? AND a.status NOT IN ('Absent','Leave')",(pid,))["v"]
 materials=one("SELECT COALESCE(SUM(mm.quantity*m.unit_cost),0)v FROM material_moves mm JOIN materials m ON m.id=mm.material_id WHERE mm.project_id=? AND mm.move_type IN ('CONSUMPTION','ISSUE','TRANSFER_OUT')",(pid,))["v"]
 subcontract=one("SELECT COALESCE(SUM(contract_value),0)v FROM subcontractors WHERE project_id=? AND status!='Cancelled'",(pid,))["v"]
 estimated=costs_total+purchases+equipment+labour+materials+subcontract
 return {"contract_value":contract,"boq_value":boq,"billed":billed,"cash_in":cash_in,"cash_out":cash_out,"direct_costs":costs_total,"purchases":purchases,"equipment_cost":equipment,"labour_cost":labour,"material_consumption_cost":materials,"subcontract_value":subcontract,"estimated_cost":estimated,"estimated_margin":contract-estimated,"remaining_contract":contract-billed}
@router.get("/projects/{pid}/cost-breakdown")
def cost_breakdown(pid:int):
 if not one("SELECT id FROM projects WHERE id=?",(pid,)): raise HTTPException(404,"Project not found")
 s=financial_summary(pid)
 return {"project_id":pid,"breakdown":{"direct":s["direct_costs"],"purchases":s["purchases"],"equipment":s["equipment_cost"],"labour":s["labour_cost"],"materials":s["material_consumption_cost"],"subcontractors":s["subcontract_value"]},"total_estimated_cost":s["estimated_cost"]}
@router.post("/payroll/periods")
def payroll_period(x:PayrollPeriodIn): return insert("payroll_periods",["period_start","period_end"],[x.period_start,x.period_end])
@router.post("/payroll/periods/{period_id}/items")
def payroll_item(period_id:int,x:PayrollItemIn):
 if not one("SELECT id FROM payroll_periods WHERE id=?",(period_id,)): raise HTTPException(404,"Payroll period not found")
 w=one("SELECT daily_rate FROM workers WHERE id=?",(x.worker_id,))
 if not w: raise HTTPException(404,"Worker not found")
 rate=x.rate_per_hour or (w["daily_rate"]/8)
 gross=x.regular_hours*rate+x.overtime_hours*rate*1.5
 return insert("payroll_items",["period_id","worker_id","regular_hours","overtime_hours","rate_per_hour","gross_amount"],[period_id,x.worker_id,x.regular_hours,x.overtime_hours,rate,gross])
@router.get("/payroll/periods/{period_id}")
def payroll_detail(period_id:int):
 p=one("SELECT * FROM payroll_periods WHERE id=?",(period_id,))
 if not p: raise HTTPException(404,"Payroll period not found")
 p["items"]=rows("SELECT pi.*,w.name worker_name,w.role FROM payroll_items pi JOIN workers w ON w.id=pi.worker_id WHERE pi.period_id=?",(period_id,))
 p["total"]=sum(x["gross_amount"] for x in p["items"])
 return p
@router.post("/payroll/periods/{period_id}/approve")
def payroll_approve(period_id:int):
    p=one("SELECT * FROM payroll_periods WHERE id=?",(period_id,))
    if not p: raise HTTPException(404,"Payroll period not found")
    if p["status"]=="Approved": return p
    total=one("SELECT COALESCE(SUM(gross_amount),0)v FROM payroll_items WHERE period_id=?",(period_id,))["v"]
    if total<=0: raise HTTPException(422,"Payroll period has no payable amount")
    with connect() as c:c.execute("UPDATE payroll_periods SET status='Approved' WHERE id=?",(period_id,))
    post_system_journal("PAYROLL-"+str(period_id),p["period_start"],"Payroll accrual "+str(period_id),None,[(account_id("5100"),total,0,"Payroll expense",None),(account_id("2100"),0,total,"Payroll payable",None)])
    audit("approve","payroll_period",period_id)
    return one("SELECT * FROM payroll_periods WHERE id=?",(period_id,))

@router.post("/change-orders")
def change_order(x:ChangeOrderIn): return insert("change_orders",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/change-orders")
def change_orders(project_id:int|None=None): return rows("SELECT * FROM change_orders WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC",(project_id,))
@router.post("/change-orders/{order_id}/approve")
def approve_change_order(order_id:int):
 if not one("SELECT id FROM change_orders WHERE id=?",(order_id,)): raise HTTPException(404,"Change order not found")
 with connect() as c:
  co=c.execute("SELECT project_id,amount,status FROM change_orders WHERE id=?",(order_id,)).fetchone()
  if co["status"]=="Approved": return one("SELECT * FROM change_orders WHERE id=?",(order_id,))
  c.execute("UPDATE change_orders SET status='Approved',approved_at=CURRENT_TIMESTAMP WHERE id=?",(order_id,))
  c.execute("UPDATE projects SET contract_value=contract_value+? WHERE id=?",(co["amount"],co["project_id"]))
 audit("approve","change_order",order_id); return one("SELECT * FROM change_orders WHERE id=?",(order_id,))
@router.post("/progress")
def progress(x:ProgressIn):
 if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)): raise HTTPException(404,"Project not found")
 b=one("SELECT project_id,unit_rate FROM boq WHERE id=?",(x.boq_id,))
 if not b or b["project_id"]!=x.project_id: raise HTTPException(404,"BOQ item not found")
 rate=b["unit_rate"] if x.unit_rate is None else x.unit_rate
 return insert("progress_entries",["project_id","boq_id","report_date","quantity","unit_rate","amount","status"],[x.project_id,x.boq_id,x.report_date,x.quantity,rate,x.quantity*rate,x.status])
@router.get("/progress")
def progress_list(project_id:int|None=None): return rows("SELECT pe.*,b.code boq_code,b.description FROM progress_entries pe JOIN boq b ON b.id=pe.boq_id WHERE pe.project_id=COALESCE(?,pe.project_id) ORDER BY report_date DESC",(project_id,))
@router.get("/projects/{pid}/progress-summary")
def progress_summary(pid:int):
 if not one("SELECT id FROM projects WHERE id=?",(pid,)): raise HTTPException(404,"Project not found")
 return rows("SELECT b.code,b.description,b.quantity planned_quantity,COALESCE(SUM(pe.quantity),0) executed_quantity,b.unit, b.quantity-COALESCE(SUM(pe.quantity),0) remaining_quantity FROM boq b LEFT JOIN progress_entries pe ON pe.boq_id=b.id AND pe.status!='Rejected' WHERE b.project_id=? GROUP BY b.id ORDER BY b.code",(pid,))
@router.post("/billing-payments")
def billing_payment(x:BillingPaymentIn):
    b=one("SELECT * FROM billings WHERE id=?",(x.billing_id,))
    if not b: raise HTTPException(404,"Billing not found")
    paid=one("SELECT COALESCE(SUM(amount),0)v FROM billing_payments WHERE billing_id=?",(x.billing_id,))["v"]
    if paid+x.amount>(b["gross_amount"]-b["gross_amount"]*b["retention_percent"]/100+b["tax_amount"])+0.000001: raise HTTPException(409,"Payment exceeds billing balance")
    p=insert("billing_payments",["billing_id","payment_date","amount","reference"],list(x.model_dump().values()))
    insert("cashflow",["project_id","entry_date","direction","category","amount","reference"],[b["project_id"],x.payment_date,"IN","Billing",x.amount,x.reference or ("PAY-"+str(p["id"]))])
    post_system_journal("PAY-"+str(p["id"]),x.payment_date,"Billing payment "+(x.reference or str(x.billing_id)),b["project_id"],[(account_id("1000"),x.amount,0,"Customer receipt",b["project_id"]),(account_id("1100"),0,x.amount,"Accounts receivable",b["project_id"])])
    return p

@router.get("/billings/{billing_id}/payments")
def billing_payments(billing_id:int):
 b=one("SELECT * FROM billings WHERE id=?",(billing_id,))
 if not b: raise HTTPException(404,"Billing not found")
 ps=rows("SELECT * FROM billing_payments WHERE billing_id=? ORDER BY payment_date",(billing_id,))
 return {"billing":b,"payments":ps,"paid":sum(x["amount"] for x in ps),"balance":b["gross_amount"]-sum(x["amount"] for x in ps)}
@router.post("/documents/upload")
async def upload_document(project_id:int|None=None,document_type:str="file",file:UploadFile=File(...)):
    if project_id is not None and not one("SELECT id FROM projects WHERE id=?",(project_id,)): raise HTTPException(404,"Project not found")
    root=Path(os.getenv("TAYEB_STORAGE_PATH",str(Path(__file__).resolve().parent/"storage"))).resolve()
    root.mkdir(parents=True,exist_ok=True)
    allowed_types={"application/pdf","image/png","image/jpeg","image/webp","application/zip",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if file.content_type not in allowed_types:
        raise HTTPException(415,"Unsupported document type")
    suffix=Path(file.filename or "").suffix[:20]
    stored_name=uuid.uuid4().hex+suffix
    target=(root/stored_name).resolve()
    if root not in target.parents: raise HTTPException(400,"Invalid file path")
    size=0
    digest=hashlib.sha256()
    try:
        with target.open("wb") as out:
            while True:
                chunk=await file.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                digest.update(chunk)
                if size>25*1024*1024:
                    target.unlink(missing_ok=True)
                    raise HTTPException(413,"File exceeds 25 MB limit")
                out.write(chunk)
    finally:
        await file.close()
    uri="file://"+str(target)
    return insert("documents",["project_id","document_type","name","storage_uri","mime_type","size_bytes","sha256"],[project_id,document_type,file.filename or stored_name,uri,file.content_type or "application/octet-stream",size,digest.hexdigest()])

@router.get("/documents/{document_id}/download")
def download_document(document_id:int):
    from fastapi.responses import FileResponse
    d=one("SELECT * FROM documents WHERE id=?",(document_id,))
    if not d: raise HTTPException(404,"Document not found")
    if not d["storage_uri"].startswith("file://"): raise HTTPException(409,"Document is stored in an external location")
    root=Path(os.getenv("TAYEB_STORAGE_PATH",str(Path(__file__).resolve().parent/"storage"))).resolve()
    target=Path(d["storage_uri"][7:]).resolve()
    if root not in target.parents or not target.is_file(): raise HTTPException(404,"Stored file not found")
    return FileResponse(target,filename=d["name"])

@router.post("/documents")
def document(x:DocumentIn): return insert("documents",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/documents")
def documents(project_id:int|None=None): return rows("SELECT * FROM documents WHERE project_id=COALESCE(?,project_id) ORDER BY created_at DESC",(project_id,))
@router.post("/issues")
def issue(x:IssueIn): return insert("issues",list(x.model_dump().keys()),list(x.model_dump().values()))
@router.get("/issues")
def issues(project_id:int|None=None): return rows("SELECT * FROM issues WHERE project_id=COALESCE(?,project_id) ORDER BY id DESC",(project_id,))
@router.post("/issues/{issue_id}/close")
def close_issue(issue_id:int):
 if not one("SELECT id FROM issues WHERE id=?",(issue_id,)): raise HTTPException(404,"Issue not found")
 with connect() as c:c.execute("UPDATE issues SET status='Closed' WHERE id=?",(issue_id,))
 audit("close","issue",issue_id); return one("SELECT * FROM issues WHERE id=?",(issue_id,))
@router.get("/audit")
def audit_log():return rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500")
@router.get("/health/modules")
def module_health():return {"projects":True,"boq":True,"labour":True,"equipment":True,"materials":True,"procurement":True,"supplier_invoices":True,"supplier_payments":True,"subcontractors":True,"site_reports":True,"billing":True,"cashflow":True,"payroll":True,"payroll_allocations":True,"change_orders":True,"progress":True,"billing_payments":True,"documents":True,"issues":True,"budgets":True,"budget_versions":True,"accounting":True,"journal_reversals":True,"cost_reconciliation":True,"bim_boundary":True}
@router.post("/accounting/fiscal-periods")
def create_fiscal_period(x:FiscalPeriodIn):
 if x.start_date>x.end_date: raise HTTPException(422,"Start date must not be after end date")
 if one("SELECT id FROM fiscal_periods WHERE start_date<=? AND end_date>=?",(x.end_date,x.start_date)): raise HTTPException(409,"Fiscal period overlaps an existing period")
 return insert("fiscal_periods",["code","start_date","end_date"],[x.code,x.start_date,x.end_date])
@router.get("/accounting/fiscal-periods")
def list_fiscal_periods(): return rows("SELECT * FROM fiscal_periods ORDER BY start_date DESC")
@router.post("/accounting/fiscal-periods/{period_id}/close")
def close_fiscal_period(period_id:int):
 p=one("SELECT * FROM fiscal_periods WHERE id=?",(period_id,))
 if not p: raise HTTPException(404,"Fiscal period not found")
 if p["status"]=="Closed": return p
 if one("SELECT id FROM journal_entries WHERE entry_date BETWEEN ? AND ? AND status!='Posted'",(p["start_date"],p["end_date"])): raise HTTPException(409,"Cannot close period with draft journal entries")
 with connect() as c:c.execute("UPDATE fiscal_periods SET status='Closed',closed_at=CURRENT_TIMESTAMP WHERE id=?",(period_id,))
 audit("close","fiscal_period",period_id); return one("SELECT * FROM fiscal_periods WHERE id=?",(period_id,))

@router.post("/budgets")
def create_budget(x:BudgetIn):
    if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)): raise HTTPException(404,"Project not found")
    return insert("budgets",["project_id","code","description","amount","category"],[x.project_id,x.code,x.description,x.amount,x.category])

@router.get("/budgets")
def list_budgets(project_id:int|None=None):
    return rows("SELECT * FROM budgets WHERE project_id=COALESCE(?,project_id) ORDER BY project_id,code",(project_id,))

@router.get("/projects/{pid}/budget-vs-actual")
def budget_vs_actual(pid:int):
    if not one("SELECT id FROM projects WHERE id=?",(pid,)): raise HTTPException(404,"Project not found")
    b=rows("SELECT category,SUM(amount) budget FROM budgets WHERE project_id=? GROUP BY category",(pid,))
    actual=rows("""SELECT category,amount FROM (
        SELECT 'Direct' category,COALESCE(SUM(amount),0) amount FROM cost_entries WHERE project_id=?
        UNION ALL SELECT 'Purchases',COALESCE(SUM(amount),0) FROM purchases WHERE project_id=?
        UNION ALL SELECT 'Equipment',COALESCE(SUM(cost),0) FROM equipment_logs WHERE project_id=?
        UNION ALL SELECT 'Labour',COALESCE(SUM(a.hours*w.daily_rate/8),0) FROM attendance a JOIN workers w ON w.id=a.worker_id WHERE a.project_id=? AND a.status NOT IN ('Absent','Leave')
    )""",(pid,pid,pid,pid))
    a={x["category"]:x["amount"] for x in actual}
    return [{"category":x["category"],"budget":x["budget"],"actual":a.get(x["category"],0),"variance":x["budget"]-a.get(x["category"],0)} for x in b]

@router.get("/accounting/profit-loss")
def profit_loss(project_id:int|None=None):
    params=(project_id,) if project_id is not None else ()
    where=" AND j.project_id=?" if project_id is not None else ""
    revenue=rows(f"""SELECT a.code,a.name,COALESCE(SUM(jl.credit-jl.debit),0) amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries j ON j.id=jl.journal_id WHERE j.status='Posted' AND a.account_type='Revenue'{where} GROUP BY a.id ORDER BY a.code""",params)
    expenses=rows(f"""SELECT a.code,a.name,COALESCE(SUM(jl.debit-jl.credit),0) amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries j ON j.id=jl.journal_id WHERE j.status='Posted' AND a.account_type='Expense'{where} GROUP BY a.id ORDER BY a.code""",params)
    rt=sum(x["amount"] for x in revenue); et=sum(x["amount"] for x in expenses)
    return {"project_id":project_id,"revenue":revenue,"expenses":expenses,"total_revenue":rt,"total_expenses":et,"net_profit":rt-et}

@router.post("/accounting/accounts")
def create_account(x:AccountIn):
 if x.account_type not in {"Asset","Liability","Equity","Revenue","Expense"}: raise HTTPException(422,"Invalid account type")
 if x.parent_id is not None and not one("SELECT id FROM accounts WHERE id=? AND active=1",(x.parent_id,)): raise HTTPException(404,"Parent account not found")
 return insert("accounts",["code","name","account_type","parent_id"],[x.code,x.name,x.account_type,x.parent_id])
@router.get("/accounting/accounts")
def list_accounts(): return rows("SELECT * FROM accounts WHERE active=1 ORDER BY code")
@router.post("/accounting/journals")
def create_journal(x:JournalEntryIn):
 if any((l.debit>0 and l.credit>0) or (l.debit==0 and l.credit==0) for l in x.lines): raise HTTPException(422,"Each line must contain either debit or credit")
 if abs(sum(l.debit for l in x.lines)-sum(l.credit for l in x.lines))>0.000001: raise HTTPException(422,"Journal is not balanced")
 with connect() as c:
  jid=c.execute("INSERT INTO journal_entries(entry_no,entry_date,description,project_id) VALUES(?,?,?,?)",(x.entry_no,x.entry_date,x.description,x.project_id)).lastrowid
  for l in x.lines:
   if not c.execute("SELECT id FROM accounts WHERE id=? AND active=1",(l.account_id,)).fetchone(): raise HTTPException(404,"Account not found")
   c.execute("INSERT INTO journal_lines(journal_id,account_id,debit,credit,description,project_id) VALUES(?,?,?,?,?,?)",(jid,l.account_id,l.debit,l.credit,l.description,l.project_id))
 audit("create","journal_entry",jid)
 return journal_detail(jid)
@router.get("/accounting/journals")
def list_journals(): return rows("SELECT * FROM journal_entries ORDER BY id DESC")
@router.get("/accounting/journals/{journal_id}")
def journal_detail(journal_id:int):
 j=one("SELECT * FROM journal_entries WHERE id=?",(journal_id,))
 if not j: raise HTTPException(404,"Journal entry not found")
 j["lines"]=rows("SELECT jl.*,a.code account_code,a.name account_name FROM journal_lines jl JOIN accounts a ON a.id=jl.account_id WHERE jl.journal_id=?",(journal_id,))
 j["total_debit"]=sum(x["debit"] for x in j["lines"]); j["total_credit"]=sum(x["credit"] for x in j["lines"])
 return j
@router.post("/accounting/journals/{journal_id}/post")
def post_journal(journal_id:int):
 j=journal_detail(journal_id)
 if abs(j["total_debit"]-j["total_credit"])>0.000001: raise HTTPException(409,"Journal is not balanced")
 fp=one("SELECT status FROM fiscal_periods WHERE start_date<=? AND end_date>=? ORDER BY id DESC LIMIT 1",(j["entry_date"],j["entry_date"]))
 if fp and fp["status"]=="Closed": raise HTTPException(409,"Fiscal period is closed")
 with connect() as c: c.execute("UPDATE journal_entries SET status='Posted',posted_at=CURRENT_TIMESTAMP WHERE id=? AND status='Draft'",(journal_id,))
 audit("post","journal_entry",journal_id)
 return journal_detail(journal_id)
@router.get("/accounting/trial-balance")
def trial_balance():
 return rows("""SELECT a.code,a.name,a.account_type,COALESCE(SUM(CASE WHEN j.status='Posted' THEN jl.debit ELSE 0 END),0) debit,COALESCE(SUM(CASE WHEN j.status='Posted' THEN jl.credit ELSE 0 END),0) credit,COALESCE(SUM(CASE WHEN j.status='Posted' THEN jl.debit-jl.credit ELSE 0 END),0) balance FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id LEFT JOIN journal_entries j ON j.id=jl.journal_id GROUP BY a.id ORDER BY a.code""")

# --- Finance/control extensions ---
@router.post("/supplier-invoices")
def supplier_invoice(x:SupplierInvoiceIn):
    if x.project_id is not None and not one("SELECT id FROM projects WHERE id=?",(x.project_id,)):
        raise HTTPException(404,"Project not found")
    if x.purchase_id is not None and not one("SELECT id FROM purchases WHERE id=?",(x.purchase_id,)):
        raise HTTPException(404,"Purchase not found")
    gross=x.amount+x.tax_amount
    i=insert("supplier_invoices",["project_id","supplier","invoice_no","invoice_date","due_date","amount","tax_amount","purchase_id"],
             [x.project_id,x.supplier,x.invoice_no,x.invoice_date,x.due_date,x.amount,x.tax_amount,x.purchase_id])
    lines=[(account_id("5200"),x.amount,0,"Supplier expense",x.project_id)]
    if x.tax_amount: lines.append((account_id("1400"),x.tax_amount,0,"Input tax",x.project_id))
    lines.append((account_id("2000"),0,gross,"Supplier payable",x.project_id))
    post_system_journal("SUPINV-"+str(i["id"]),x.invoice_date,"Supplier invoice "+x.invoice_no,x.project_id,lines)
    return one("SELECT * FROM supplier_invoices WHERE id=?",(i["id"],))

@router.get("/supplier-invoices")
def supplier_invoices(project_id:int|None=None):
    return rows("""SELECT si.*,COALESCE((SELECT SUM(sp.amount) FROM supplier_payments sp WHERE sp.supplier_invoice_id=si.id),0) paid
                   FROM supplier_invoices si WHERE si.project_id=COALESCE(?,si.project_id) ORDER BY si.id DESC""",(project_id,))

@router.get("/supplier-invoices/{invoice_id}")
def supplier_invoice_detail(invoice_id:int):
    i=one("SELECT * FROM supplier_invoices WHERE id=?",(invoice_id,))
    if not i: raise HTTPException(404,"Supplier invoice not found")
    ps=rows("SELECT * FROM supplier_payments WHERE supplier_invoice_id=? ORDER BY payment_date",(invoice_id,))
    i["payments"]=ps
    i["paid"]=sum(x["amount"] for x in ps)
    i["balance"]=i["amount"]+i["tax_amount"]-i["paid"]
    return i

@router.post("/supplier-payments")
def supplier_payment(x:SupplierPaymentIn):
    i=one("SELECT * FROM supplier_invoices WHERE id=?",(x.supplier_invoice_id,))
    if not i: raise HTTPException(404,"Supplier invoice not found")
    paid=one("SELECT COALESCE(SUM(amount),0)v FROM supplier_payments WHERE supplier_invoice_id=?",(x.supplier_invoice_id,))["v"]
    gross=i["amount"]+i["tax_amount"]
    if paid+x.amount>gross+0.000001: raise HTTPException(409,"Payment exceeds supplier balance")
    p=insert("supplier_payments",["supplier_invoice_id","payment_date","amount","reference"],list(x.model_dump().values()))
    insert("cashflow",["project_id","entry_date","direction","category","amount","reference"],
           [i["project_id"],x.payment_date,"OUT","Supplier payment",x.amount,x.reference or "SUPPAY-"+str(p["id"])])
    post_system_journal("SUPPAY-"+str(p["id"]),x.payment_date,"Supplier payment "+i["invoice_no"],i["project_id"],
                        [(account_id("2000"),x.amount,0,"Supplier payable settlement",i["project_id"]),
                         (account_id("1000"),0,x.amount,"Cash payment",i["project_id"])])
    new_paid=paid+x.amount
    with connect() as c:
        c.execute("UPDATE supplier_invoices SET status=? WHERE id=?",("Paid" if new_paid>=gross-0.000001 else "Partially Paid",x.supplier_invoice_id))
    return p

@router.post("/payroll/allocations")
def payroll_allocate(x:PayrollAllocationIn):
    item=one("""SELECT pi.*,pp.status period_status FROM payroll_items pi
                JOIN payroll_periods pp ON pp.id=pi.period_id WHERE pi.id=?""",(x.payroll_item_id,))
    if not item: raise HTTPException(404,"Payroll item not found")
    if item["period_status"]!="Approved": raise HTTPException(409,"Payroll period must be approved before allocation")
    if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)): raise HTTPException(404,"Project not found")
    already=one("SELECT COALESCE(SUM(amount),0)v FROM payroll_allocations WHERE payroll_item_id=?",(x.payroll_item_id,))["v"]
    if already+x.amount>item["gross_amount"]+0.000001: raise HTTPException(409,"Allocation exceeds payroll item")
    if x.amount<=0: raise HTTPException(422,"Allocation amount must be positive")
    out=insert("payroll_allocations",["payroll_item_id","project_id","hours","amount"],list(x.model_dump().values()))
    insert("cost_entries",["project_id","entry_date","cost_type","description","amount","reference"],
           [x.project_id,item["period_start"] if "period_start" in item else one("SELECT period_start FROM payroll_periods WHERE id=?",(item["period_id"],))["period_start"],
            "Payroll","Allocated payroll",x.amount,"PAYITEM-"+str(x.payroll_item_id)])
    return out

@router.get("/payroll/allocations")
def payroll_allocations(project_id:int|None=None):
    return rows("""SELECT pa.*,pi.worker_id,w.name worker_name,pp.period_start,pp.period_end
                   FROM payroll_allocations pa JOIN payroll_items pi ON pi.id=pa.payroll_item_id
                   JOIN workers w ON w.id=pi.worker_id JOIN payroll_periods pp ON pp.id=pi.period_id
                   WHERE pa.project_id=COALESCE(?,pa.project_id) ORDER BY pa.id DESC""",(project_id,))

@router.post("/budgets/versions")
def create_budget_version(x:BudgetVersionIn):
    if not one("SELECT id FROM projects WHERE id=?",(x.project_id,)): raise HTTPException(404,"Project not found")
    current=one("SELECT COALESCE(MAX(version_no),0)v FROM budget_versions WHERE project_id=?",(x.project_id,))["v"]
    with connect() as c:
        vid=c.execute("INSERT INTO budget_versions(project_id,version_no,notes) VALUES(?,?,?)",(x.project_id,current+1,x.notes)).lastrowid
        items=c.execute("SELECT code,description,amount,category FROM budgets WHERE project_id=? ORDER BY code",(x.project_id,)).fetchall()
        for it in items:
            c.execute("INSERT INTO budget_version_items(version_id,code,description,amount,category) VALUES(?,?,?,?,?)",(vid,it["code"],it["description"],it["amount"],it["category"]))
    audit("create","budget_version",vid)
    return {"id":vid,"project_id":x.project_id,"version_no":current+1,"notes":x.notes,"items":rows("SELECT * FROM budget_version_items WHERE version_id=?",(vid,))}

@router.get("/budgets/versions")
def budget_versions(project_id:int|None=None):
    return rows("SELECT * FROM budget_versions WHERE project_id=COALESCE(?,project_id) ORDER BY project_id,version_no DESC",(project_id,))

@router.get("/budgets/versions/{version_id}")
def budget_version_detail(version_id:int):
    v=one("SELECT * FROM budget_versions WHERE id=?",(version_id,))
    if not v: raise HTTPException(404,"Budget version not found")
    v["items"]=rows("SELECT * FROM budget_version_items WHERE version_id=? ORDER BY code",(version_id,))
    return v

@router.post("/accounting/journals/{journal_id}/reverse")
def reverse_journal(journal_id:int,x:JournalReversalIn):
    j=journal_detail(journal_id)
    if j["status"]!="Posted": raise HTTPException(409,"Only posted journals can be reversed")
    if one("SELECT id FROM journal_reversals WHERE original_journal_id=?",(journal_id,)): raise HTTPException(409,"Journal already reversed")
    lines=[(l["account_id"],l["credit"],l["debit"],"Reversal: "+(l["description"] or ""),l["project_id"]) for l in j["lines"]]
    from datetime import date
    reversal=post_system_journal("REV-"+str(journal_id),date.today().isoformat(),"Reversal of "+j["entry_no"]+": "+x.reason,j["project_id"],lines)
    with connect() as c:
        c.execute("INSERT INTO journal_reversals(original_journal_id,reversal_journal_id,reason) VALUES(?,?,?)",(journal_id,reversal,x.reason))
    audit("reverse","journal_entry",journal_id)
    return journal_detail(reversal)

@router.get("/accounting/journals/{journal_id}/reversal")
def journal_reversal(journal_id:int):
    r=one("SELECT * FROM journal_reversals WHERE original_journal_id=?",(journal_id,))
    if not r: raise HTTPException(404,"No reversal found")
    return r

@router.get("/projects/{pid}/cost-reconciliation")
def cost_reconciliation(pid:int):
    if not one("SELECT id FROM projects WHERE id=?",(pid,)): raise HTTPException(404,"Project not found")
    operational=financial_summary(pid)
    accounting=one("""SELECT COALESCE(SUM(jl.debit-jl.credit),0)v
                     FROM journal_lines jl JOIN journal_entries j ON j.id=jl.journal_id
                     JOIN accounts a ON a.id=jl.account_id
                     WHERE j.status='Posted' AND j.project_id=? AND a.account_type='Expense'""",(pid,))["v"]
    return {"project_id":pid,"operational_estimated_cost":operational["estimated_cost"],"posted_accounting_expense":accounting,"variance":operational["estimated_cost"]-accounting}

@router.get("/accounting/balance-sheet")
def balance_sheet():
    return rows("""SELECT a.code,a.name,a.account_type,
                   COALESCE(SUM(CASE WHEN j.status='Posted' THEN jl.debit-jl.credit ELSE 0 END),0) balance
                   FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id
                   LEFT JOIN journal_entries j ON j.id=jl.journal_id
                   WHERE a.account_type IN ('Asset','Liability','Equity')
                   GROUP BY a.id ORDER BY a.code""")