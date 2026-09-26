from fastapi.testclient import TestClient
from app.main import app
import app.db as db

def test_health():
    c=TestClient(app)
    assert c.get("/health").json()["status"]=="ok"

def test_project_flow():
    c=TestClient(app)
    code="TEST-"+__import__("uuid").uuid4().hex[:8]
    r=c.post("/api/projects",json={"code":code,"name":"Test project","client":"Client","contract_value":1000})
    assert r.status_code==200
    pid=r.json()["id"]
    r=c.post("/api/boq",json={"project_id":pid,"code":"01","description":"Concrete","unit":"m3","quantity":10,"unit_rate":50})
    assert r.status_code==200 and r.json()["amount"]==500
    r=c.get(f"/api/projects/{pid}")
    assert r.status_code==200 and len(r.json()["boq"])==1
