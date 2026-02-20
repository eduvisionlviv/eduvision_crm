from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra='ignore')

class MFPartnersSchema(BaseSchema):
    id: str
    name: str
    status: str = "active"
    frozen_at: Optional[str] = None
    acting_mf_contact: Optional[str] = None

class AuthAccountsSchema(BaseSchema):
    id: str
    email: str
    role_id: str = Field(alias="role") 
    is_active: bool = True
    frozen_at: Optional[str] = None
    preferred_language: str = "uk"

class LCSchema(BaseSchema):
    id: str
    mf_id: str
    name: str = Field(alias="lc_name")
    status: str = "active"

class EmployeeLCAccessSchema(BaseSchema):
    id: str
    employee_id: str
    lc_id: str
    mf_id: str
    is_primary: bool = False
