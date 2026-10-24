from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_superuser: bool = False

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    is_superuser: bool
    is_active: bool
    created_at: datetime

class TenantCreateRequest(BaseModel):
    name: str
    slug: str

class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime

class TenantMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    user_id: str
    role: str
    tenant: TenantResponse

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in_seconds: int
    user: UserResponse
    tenants: List[TenantMembershipResponse]
