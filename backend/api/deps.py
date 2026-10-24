from __future__ import annotations
from typing import Optional
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.models.tenant import User, Tenant, TenantMembership

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired authentication token',
            headers={'WWW-Authenticate': 'Bearer'}
        )
    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Malformed token payload'
        )
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    user = db.execute(stmt).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User not found or inactive'
        )
    return user

def get_current_tenant(
    request: Request,
    x_tenant_id: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Tenant:
    requested_tenant_id = x_tenant_id or request.query_params.get('tenant_id')
    
    if requested_tenant_id:
        stmt = select(Tenant).where(Tenant.id == requested_tenant_id, Tenant.is_active == True)
        tenant = db.execute(stmt).scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{requested_tenant_id}' not found or inactive"
            )
        
        if not current_user.is_superuser:
            mem_stmt = select(TenantMembership).where(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.user_id == current_user.id
            )
            membership = db.execute(mem_stmt).scalar_one_or_none()
            if not membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-tenant access forbidden. You are not a member of this tenant."
                )
        return tenant
    
    mem_stmt = select(TenantMembership).where(TenantMembership.user_id == current_user.id)
    memberships = list(db.execute(mem_stmt).scalars().all())
    if not memberships:
        if current_user.is_superuser:
            t_stmt = select(Tenant).where(Tenant.is_active == True).limit(1)
            tenant = db.execute(t_stmt).scalar_one_or_none()
            if tenant:
                return tenant
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='No authorized tenant memberships found for this user'
        )
    
    t_stmt = select(Tenant).where(Tenant.id == memberships[0].tenant_id)
    tenant = db.execute(t_stmt).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tenant not found')
    return tenant

class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
        current_tenant: Tenant = Depends(get_current_tenant),
        db: Session = Depends(get_db)
    ) -> bool:
        if current_user.is_superuser:
            return True
        mem_stmt = select(TenantMembership).where(
            TenantMembership.tenant_id == current_tenant.id,
            TenantMembership.user_id == current_user.id
        )
        membership = db.execute(mem_stmt).scalar_one_or_none()
        if not membership or membership.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {self.allowed_roles}"
            )
        return True

require_admin = RoleChecker(['OWNER', 'ADMIN'])
require_operator = RoleChecker(['OWNER', 'ADMIN', 'OPERATOR'])
require_viewer = RoleChecker(['OWNER', 'ADMIN', 'OPERATOR', 'VIEWER'])
