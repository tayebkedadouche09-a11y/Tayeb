import os,tempfile,importlib,uuid
os.environ["TAYEB_DB_PATH"]=os.path.join(tempfile.gettempdir(),"tayeb-test-"+uuid.uuid4().hex+".db")
from app import db
db.init_db()
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def test_health(): assert c.get("/health").json()["status"]=="ok"
def test_commercial_flow():
 p=c.post("/api/projects",json={"code":"T-"+uuid.uuid4().hex[:8],"name":"Commercial Build","contract_value":100000}).json();pid=p["id"]
 assert c.post("/api/boq",json={"project_id":pid,"code":"01","description":"Concrete","quantity":10,"unit_rate":50}).status_code==200
 w=c.post("/api/workers",json={"code":"W-"+uuid.uuid4().hex[:6],"name":"Worker","daily_rate":100}).json()
 assert c.post("/api/attendance",json={"project_id":pid,"worker_id":w["id"],"work_date":"2026-09-26"}).status_code==200
 m=c.post("/api/materials",json={"code":"MAT-"+uuid.uuid4().hex[:6],"name":"Cement","stock":100,"unit_cost":500}).json()
 assert c.post("/api/materials/move",json={"project_id":pid,"material_id":m["id"],"quantity":10}).status_code==200
 assert c.get("/api/materials").json()[0]["stock"]==90
 e=c.post("/api/equipment",json={"code":"EQ-"+uuid.uuid4().hex[:6],"name":"Excavator","hourly_rate":200}).json()
 assert c.post("/api/equipment/logs",json={"equipment_id":e["id"],"project_id":pid,"work_date":"2026-09-26","hours":3}).json()["cost"]==600
 inv=c.post("/api/billings",json={"project_id":pid,"invoice_no":"I-"+uuid.uuid4().hex[:6],"gross_amount":1000}).json()
 assert inv["retention_amount"]==50 and inv["net_amount"]==950
 assert c.get(f"/api/projects/{pid}").json()["boq"][0]["amount"]==500
def test_new_workflows():
 p=c.post("/api/projects",json={"code":"N-"+uuid.uuid4().hex[:8],"name":"New Workflows","contract_value":50000}).json(); pid=p["id"]
 b=c.post("/api/boq",json={"project_id":pid,"code":"01","description":"Wall","quantity":100,"unit_rate":20}).json()
 w=c.post("/api/workers",json={"code":"PW-"+uuid.uuid4().hex[:6],"name":"Payroll Worker","daily_rate":160}).json()
 period=c.post("/api/payroll/periods",json={"period_start":"2026-09-01","period_end":"2026-09-30"}).json()
 item=c.post(f"/api/payroll/periods/{period['id']}/items",json={"worker_id":w["id"],"regular_hours":8}).json()
 assert item["gross_amount"]==160
 assert c.post("/api/progress",json={"project_id":pid,"boq_id":b["id"],"report_date":"2026-09-26","quantity":10}).status_code==200
 co=c.post("/api/change-orders",json={"project_id":pid,"code":"CO-01","description":"Extra work","amount":1000}).json()
 assert c.post(f"/api/change-orders/{co['id']}/approve").status_code==200
 inv=c.post("/api/billings",json={"project_id":pid,"invoice_no":"NP-"+uuid.uuid4().hex[:6],"gross_amount":2000}).json()
 pay=c.post("/api/billing-payments",json={"billing_id":inv["id"],"payment_date":"2026-09-26","amount":500}).status_code
 assert pay==200
 assert c.post("/api/documents",json={"project_id":pid,"document_type":"plan","name":"plan.pdf","storage_uri":"s3://docs/plan.pdf"}).status_code==200
 assert c.post("/api/issues",json={"project_id":pid,"title":"Delay"}).status_code==200

def test_accounting_flow():
 p=c.post("/api/projects",json={"code":"AC-"+uuid.uuid4().hex[:8],"name":"Accounting Project","contract_value":10000}).json()
 cash=c.post("/api/accounting/accounts",json={"code":"1"+uuid.uuid4().hex[:5],"name":"Cash","account_type":"Asset"}).json()
 rev=c.post("/api/accounting/accounts",json={"code":"4"+uuid.uuid4().hex[:5],"name":"Revenue","account_type":"Revenue"}).json()
 j=c.post("/api/accounting/journals",json={"entry_no":"JE-"+uuid.uuid4().hex[:8],"entry_date":"2026-09-26","project_id":p["id"],"lines":[{"account_id":cash["id"],"debit":1000},{"account_id":rev["id"],"credit":1000}]}).json()
 assert j["total_debit"]==1000 and j["total_credit"]==1000
 assert c.post(f"/api/accounting/journals/{j['id']}/post").json()["status"]=="Posted"
 tb=c.get("/api/accounting/trial-balance").json()
 assert any(x["code"]==cash["code"] and x["balance"]==1000 for x in tb)

def test_finance_integrations():
    p=c.post("/api/projects",json={"code":"FI-"+uuid.uuid4().hex[:8],"name":"Finance Integrations","contract_value":10000}).json()
    inv=c.post("/api/billings",json={"project_id":p["id"],"invoice_no":"FI-I-"+uuid.uuid4().hex[:6],"gross_amount":1000}).json()
    assert c.post("/api/billing-payments",json={"billing_id":inv["id"],"payment_date":"2026-09-26","amount":400}).status_code==200
    pl=c.get("/api/accounting/profit-loss").json()
    assert pl["total_revenue"] >= 0
    b=c.post("/api/budgets",json={"project_id":p["id"],"code":"LAB","amount":500,"category":"Labour"}).json()
    assert b["amount"]==500
    co=c.post("/api/change-orders",json={"project_id":p["id"],"code":"CO-FI","description":"Extra","amount":250}).json()
    assert c.post(f"/api/change-orders/{co['id']}/approve").json()["status"]=="Approved"
    assert c.get(f"/api/projects/{p['id']}").json()["contract_value"]==10250

def test_fiscal_period_and_invoice_accounting():
 p=c.post("/api/projects",json={"code":"FP-"+uuid.uuid4().hex[:8],"name":"Fiscal Project","contract_value":10000}).json()
 fp=c.post("/api/accounting/fiscal-periods",json={"code":"FP-"+uuid.uuid4().hex[:6],"start_date":"2026-09-01","end_date":"2026-09-30"}).json()
 inv=c.post("/api/billings",json={"project_id":p["id"],"invoice_no":"VAT-"+uuid.uuid4().hex[:6],"gross_amount":1000,"retention_percent":5,"tax_amount":190}).json()
 assert inv["net_amount"]==1140
 assert c.post("/api/billing-payments",json={"billing_id":inv["id"],"payment_date":"2026-09-26","amount":1140}).status_code==200
 assert c.post(f"/api/accounting/fiscal-periods/{fp['id']}/close").status_code==200
