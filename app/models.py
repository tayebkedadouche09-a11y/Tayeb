from pydantic import BaseModel, Field
from typing import Optional

class ProjectIn(BaseModel):
    code: str = Field(min_length=1,max_length=40)
    name: str
    client: str = ""
    location: str = ""
    contract_value: float = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class BOQIn(BaseModel):
    project_id: int
    code: str
    description: str
    unit: str = "unit"
    quantity: float = 0
    unit_rate: float = 0
    category: str = "General"

class ResourceIn(BaseModel):
    kind: str
    code: str
    name: str
    unit: str = "unit"
    unit_cost: float = 0

class DailyReportIn(BaseModel):
    project_id: int
    report_date: str
    summary: str = ""
    progress_percent: float = 0
    labour_count: int = 0
    material_cost: float = 0
    equipment_cost: float = 0
    notes: str = ""

class TaskIn(BaseModel):
    project_id: int
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    progress: float = 0

class BillingIn(BaseModel):
    project_id: int
    invoice_no: str
    gross_amount: float
    retention_percent: float = 5
    tax_amount: float = 0

class BIMJobIn(BaseModel):
    project_id: int
    source_type: str
    source_uri: str
    job_type: str = "takeoff"
