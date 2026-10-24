from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.security import create_access_token
from backend.models.tenant import User, Tenant, TenantMembership
from backend.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserCreateRequest,
    UserResponse,
    TenantResponse,
    TenantCreateRequest,
    TenantMembershipResponse
)
from backend.services.auth_service import (
    authenticate_user,
    create_user,
    create_tenant,
    add_tenant_membership,
    get_user_memberships,
    get_user_by_email
)
from backend.api.deps import get_current_user

router = APIRouter(prefix='/auth', tags=['Authentication'])

@router.post('/login', response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect email or password',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    
    memberships = get_user_memberships(db, user.id)
    token = create_access_token({'sub': user.id, 'email': user.email})
    
    membership_responses = []
    for m in memberships:
        stmt = select(Tenant).where(Tenant.id == m.tenant_id)
        t = db.execute(stmt).scalar_one_or_none()
        if t:
            membership_responses.append(
                TenantMembershipResponse(
                    id=m.id,
                    tenant_id=m.tenant_id,
                    user_id=m.user_id,
                    role=m.role,
                    tenant=TenantResponse.model_validate(t)
                )
            )

    return TokenResponse(
        access_token=token,
        token_type='bearer',
        expires_in_seconds=86400,
        user=UserResponse.model_validate(user),
        tenants=membership_responses
    )

@router.post('/register', response_model=UserResponse)
def register(data: UserCreateRequest, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{data.email}' already exists"
        )
    user = create_user(db, data.email, data.password, data.full_name, data.is_superuser)
    return UserResponse.model_validate(user)

@router.get('/me', response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@router.get('/tenants', response_model=List[TenantMembershipResponse])
def get_user_tenants(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = get_user_memberships(db, current_user.id)
    res = []
    for m in memberships:
        stmt = select(Tenant).where(Tenant.id == m.tenant_id)
        t = db.execute(stmt).scalar_one_or_none()
        if t:
            res.append(
                TenantMembershipResponse(
                    id=m.id,
                    tenant_id=m.tenant_id,
                    user_id=m.user_id,
                    role=m.role,
                    tenant=TenantResponse.model_validate(t)
                )
            )
    return res

@router.post('/tenants', response_model=TenantResponse)
def create_new_tenant(
    data: TenantCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    stmt = select(Tenant).where(Tenant.slug == data.slug.lower().strip())
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant slug '{data.slug}' already exists"
        )
    tenant = create_tenant(db, data.name, data.slug)
    add_tenant_membership(db, tenant.id, current_user.id, role='OWNER')
    return TenantResponse.model_validate(tenant)
