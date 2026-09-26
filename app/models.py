from pydantic import BaseModel,Field
from typing import Optional
class ProjectIn(BaseModel): code:str=Field(min_length=1,max_length=40); name:str; client:str=""; location:str=""; contract_value:float=Field(0,ge=0); start_date:Optional[str]=None; end_date:Optional[str]=None
class TaskIn(BaseModel): project_id:int; name:str; start_date:Optional[str]=None; end_date:Optional[str]=None; progress:float=Field(0,ge=0,le=100)
class BOQIn(BaseModel): project_id:int; code:str; description:str; unit:str="unit"; quantity:float=Field(0,ge=0); unit_rate:float=Field(0,ge=0); category:str="General"
class WorkerIn(BaseModel): code:str; name:str; role:str="Worker"; phone:str=""; daily_rate:float=Field(0,ge=0)
class EquipmentIn(BaseModel): code:str; name:str; equipment_type:str="Machine"; hourly_rate:float=Field(0,ge=0); status:str="Available"
class EquipmentLogIn(BaseModel): equipment_id:int; project_id:int; work_date:str; hours:float=Field(0,ge=0); notes:str=""
class MaterialIn(BaseModel): code:str; name:str; unit:str="unit"; unit_cost:float=Field(0,ge=0); stock:float=Field(0,ge=0); reorder_level:float=Field(0,ge=0)
class DailyReportIn(BaseModel): project_id:int; report_date:str; summary:str=""; progress_percent:float=Field(0,ge=0,le=100); labour_count:int=Field(0,ge=0); material_cost:float=Field(0,ge=0); equipment_cost:float=Field(0,ge=0); notes:str=""
class AttendanceIn(BaseModel): project_id:int; worker_id:int; work_date:str; hours:float=Field(8,ge=0); status:str="Present"
class MaterialMoveIn(BaseModel): project_id:int; material_id:int; quantity:float=Field(gt=0); move_type:str="CONSUMPTION"; reference:str=""
class PurchaseIn(BaseModel): project_id:int; supplier:str; reference:str; amount:float=Field(0,ge=0); status:str="Draft"
class SubcontractIn(BaseModel): project_id:int; company:str; scope:str; contract_value:float=Field(0,ge=0); retention_percent:float=Field(5,ge=0,le=100)
class BillingIn(BaseModel): project_id:int; invoice_no:str; gross_amount:float=Field(gt=0); retention_percent:float=Field(5,ge=0,le=100); tax_amount:float=Field(0,ge=0)
class CashflowIn(BaseModel): project_id:int; entry_date:str; direction:str; category:str; amount:float=Field(gt=0); reference:str=""
class BIMJobIn(BaseModel): project_id:int; source_type:str; source_uri:str; job_type:str="takeoff"