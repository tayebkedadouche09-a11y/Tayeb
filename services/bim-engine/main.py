from fastapi import FastAPI
from pydantic import BaseModel
import uuid
app=FastAPI(title="Tayeb BIM Engine Boundary")
class Job(BaseModel):
    project_id:int
    source_type:str
    source_uri:str
    job_type:str="takeoff"
@app.get("/health")
def health(): return {"status":"ok","service":"bim-engine"}
@app.post("/api/v1/jobs")
def job(x:Job):
    return {"job_id":str(uuid.uuid4()),"status":"queued","project_id":x.project_id,"job_type":x.job_type,
            "pipeline":["ingest","validate","extract-elements","quantity-takeoff","boq-export"]}
