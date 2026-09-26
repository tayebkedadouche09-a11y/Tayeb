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