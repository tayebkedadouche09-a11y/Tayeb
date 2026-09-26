import os,tempfile,importlib,uuid
os.environ["TAYEB_DB_PATH"]=os.path.join(tempfile.gettempdir(),"tayeb-test-"+uuid.uuid4().hex+".db")
from app import db
db.init_db()
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)

import pytest
@pytest.fixture(autouse=True)
def reset_test_database():
    try:
        db.DB.unlink()
    except FileNotFoundError:
        pass
    db.init_db()
    yield
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

def test_supplier_payroll_budget_and_reversal():
    p=c.post("/api/projects",json={"code":"EXT-"+uuid.uuid4().hex[:8],"name":"Extended Finance","contract_value":20000}).json()
    si=c.post("/api/supplier-invoices",json={"project_id":p["id"],"supplier":"Supplier A","invoice_no":"S-"+uuid.uuid4().hex[:8],"invoice_date":"2026-09-26","amount":1000,"tax_amount":190}).json()
    assert si["status"]=="Open"
    assert c.post("/api/supplier-payments",json={"supplier_invoice_id":si["id"],"payment_date":"2026-09-26","amount":1190}).status_code==200
    assert c.get(f"/api/supplier-invoices/{si['id']}").json()["balance"]==0
    w=c.post("/api/workers",json={"code":"EW-"+uuid.uuid4().hex[:6],"name":"Allocated Worker","daily_rate":160}).json()
    period=c.post("/api/payroll/periods",json={"period_start":"2026-09-01","period_end":"2026-09-30"}).json()
    item=c.post(f"/api/payroll/periods/{period['id']}/items",json={"worker_id":w["id"],"regular_hours":16}).json()
    assert c.post(f"/api/payroll/periods/{period['id']}/approve").status_code==200
    assert c.post("/api/payroll/allocations",json={"payroll_item_id":item["id"],"project_id":p["id"],"hours":16,"amount":320}).status_code==200
    c.post("/api/budgets",json={"project_id":p["id"],"code":"MAT","amount":1000,"category":"Materials"})
    ver=c.post("/api/budgets/versions",json={"project_id":p["id"],"notes":"Baseline"}).json()
    assert ver["version_no"]==1 and len(ver["items"])==1
    cash=c.post("/api/accounting/accounts",json={"code":"REV-"+uuid.uuid4().hex[:5],"name":"Reversal Cash","account_type":"Asset"}).json()
    rev=c.post("/api/accounting/accounts",json={"code":"REV-R-"+uuid.uuid4().hex[:5],"name":"Reversal Revenue","account_type":"Revenue"}).json()
    j=c.post("/api/accounting/journals",json={"entry_no":"RJE-"+uuid.uuid4().hex[:8],"entry_date":"2026-09-26","lines":[{"account_id":cash["id"],"debit":100},{"account_id":rev["id"],"credit":100}]}).json()
    c.post(f"/api/accounting/journals/{j['id']}/post")
    rj=c.post(f"/api/accounting/journals/{j['id']}/reverse",json={"reason":"Correction"}).json()
    assert rj["status"]=="Posted" and rj["total_debit"]==100 and rj["total_credit"]==100
