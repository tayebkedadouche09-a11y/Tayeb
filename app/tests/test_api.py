from fastapi.testclient import TestClient
from app.main import app
import uuid
c=TestClient(app)
def test_health():assert c.get("/health").json()["status"]=="ok"
def test_core_flow():
 code="T-"+uuid.uuid4().hex[:8]
 p=c.post("/api/projects",json={"code":code,"name":"Commercial Build","contract_value":100000}).json(); pid=p["id"]
 assert c.post("/api/boq",json={"project_id":pid,"code":"01","description":"Concrete","quantity":10,"unit_rate":50}).status_code==200
 w=c.post("/api/workers",json={"code":"W-"+uuid.uuid4().hex[:6],"name":"Worker","daily_rate":100}).json()
 assert c.post("/api/attendance",json={"project_id":pid,"worker_id":w["id"],"work_date":"2026-09-26"}).status_code==200
 m=c.post("/api/materials",json={"code":"MAT-"+uuid.uuid4().hex[:6],"name":"Cement","stock":100}).json()
 assert c.post("/api/materials/move",json={"project_id":pid,"material_id":m["id"],"quantity":10}).status_code==200
 assert c.post("/api/billings",json={"project_id":pid,"invoice_no":"I-"+uuid.uuid4().hex[:6],"gross_amount":1000}).status_code==200
 assert c.get(f"/api/projects/{pid}").json()["boq"][0]["amount"]==500
