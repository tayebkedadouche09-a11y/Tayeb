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
class CostIn(BaseModel): project_id:int; entry_date:str; cost_type:str; description:str=""; amount:float=Field(gt=0); reference:str=""
class LoginIn(BaseModel): username:str=Field(min_length=1,max_length=80); password:str=Field(min_length=8,max_length=256)
class UserIn(BaseModel): username:str=Field(min_length=1,max_length=80); password:str=Field(min_length=8,max_length=256); role:str="viewer"
class PurchaseItemIn(BaseModel): material_id:Optional[int]=None; description:str=""; quantity:float=Field(gt=0); unit_rate:float=Field(ge=0)

class PayrollPeriodIn(BaseModel): period_start:str; period_end:str
class PayrollItemIn(BaseModel): worker_id:int; regular_hours:float=Field(0,ge=0); overtime_hours:float=Field(0,ge=0); rate_per_hour:float=Field(0,ge=0)
class ChangeOrderIn(BaseModel): project_id:int; code:str; description:str; amount:float=0; status:str="Draft"
class ProgressIn(BaseModel): project_id:int; boq_id:int; report_date:str; quantity:float=Field(gt=0); unit_rate:float=Field(ge=0); status:str="Draft"
class BillingPaymentIn(BaseModel): billing_id:int; payment_date:str; amount:float=Field(gt=0); reference:str=""
class DocumentIn(BaseModel): project_id:Optional[int]=None; document_type:str; name:str; storage_uri:str; version:int=Field(1,ge=1)
class IssueIn(BaseModel): project_id:int; title:str; description:str=""; severity:str="Medium"; status:str="Open"; due_date:Optional[str]=None

class AccountIn(BaseModel):
 code:str; name:str; account_type:str; parent_id:Optional[int]=None
class JournalLineIn(BaseModel):
 account_id:int; debit:float=Field(0,ge=0); credit:float=Field(0,ge=0); description:str=""; project_id:Optional[int]=None
class JournalEntryIn(BaseModel):
 entry_no:str; entry_date:str; description:str=""; project_id:Optional[int]=None; lines:list[JournalLineIn]=Field(min_length=2)
