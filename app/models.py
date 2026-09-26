from pydantic import BaseModel,Field
from typing import Optional

class ProjectIn(BaseModel):
 code:str=Field(min_length=1,max_length=40); name:str; client:str=""; location:str=""; contract_value:float=0; start_date:Optional[str]=None; end_date:Optional[str]=None
class TaskIn(BaseModel):
 project_id:int; name:str; start_date:Optional[str]=None; end_date:Optional[str]=None; progress:float=Field(0,ge=0,le=100)
class BOQIn(BaseModel):
 project_id:int; code:str; description:str; unit:str="unit"; quantity:float=0; unit_rate:float=0; category:str="General"
class ResourceIn(BaseModel):
 kind:str; code:str; name:str; unit:str="unit"; unit_cost:float=0
class WorkerIn(BaseModel):
 code:str; name:str; role:str="Worker"; phone:str=""; daily_rate:float=0
class EquipmentIn(BaseModel):
 code:str; name:str; equipment_type:str="Machine"; hourly_rate:float=0; status:str="Available"
class MaterialIn(BaseModel):
 code:str; name:str; unit:str="unit"; unit_cost:float=0; stock:float=0; reorder_level:float=0
class DailyReportIn(BaseModel):
 project_id:int; report_date:str; summary:str=""; progress_percent:float=0; labour_count:int=0; material_cost:float=0; equipment_cost:float=0; notes:str=""
class AttendanceIn(BaseModel):
 project_id:int; worker_id:int; work_date:str; hours:float=8; status:str="Present"
class MaterialMoveIn(BaseModel):
 project_id:int; material_id:int; quantity:float; move_type:str="CONSUMPTION"; reference:str=""
class PurchaseIn(BaseModel):
 project_id:int; supplier:str; reference:str; amount:float; status:str="Draft"
class SubcontractIn(BaseModel):
 project_id:int; company:str; scope:str; contract_value:float=0; retention_percent:float=5
class BillingIn(BaseModel):
 project_id:int; invoice_no:str; gross_amount:float; retention_percent:float=5; tax_amount:float=0
class CashflowIn(BaseModel):
 project_id:int; entry_date:str; direction:str; category:str; amount:float; reference:str=""
class BIMJobIn(BaseModel):
 project_id:int; source_type:str; source_uri:str; job_type:str="takeoff"