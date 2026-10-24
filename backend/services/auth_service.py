from __future__ import annotations
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from backend.models.tenant import User, Tenant, TenantMembership
from backend.core.security import hash_password, verify_password

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email.lower().strip())
    return db.execute(stmt).scalar_one_or_none()

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_user(db: Session, email: str, password: str, full_name: str, is_superuser: bool = False) -> User:
    hashed = hash_password(password)
    user = User(
        email=email.lower().strip(),
        hashed_password=hashed,
        full_name=full_name.strip(),
        is_superuser=is_superuser,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def create_tenant(db: Session, name: str, slug: str) -> Tenant:
    tenant = Tenant(
        name=name.strip(),
        slug=slug.lower().strip(),
        is_active=True
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant

def add_tenant_membership(db: Session, tenant_id: str, user_id: str, role: str = 'ADMIN') -> TenantMembership:
    membership = TenantMembership(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role.upper()
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership

def get_user_memberships(db: Session, user_id: str) -> List[TenantMembership]:
    stmt = select(TenantMembership).where(TenantMembership.user_id == user_id)
    return list(db.execute(stmt).scalars().all())

def seed_default_admin(db: Session) -> Tuple[User, Tenant]:
    admin_email = 'admin@zeddigital.com'
    user = get_user_by_email(db, admin_email)
    if not user:
        user = create_user(db, admin_email, 'Admin@123456', 'System Administrator', is_superuser=True)
    
    tenant_slug = 'default-facility'
    stmt = select(Tenant).where(Tenant.slug == tenant_slug)
    tenant = db.execute(stmt).scalar_one_or_none()
    if not tenant:
        tenant = create_tenant(db, 'Zed Enterprise Facility', tenant_slug)
    
    stmt = select(TenantMembership).where(
        TenantMembership.tenant_id == tenant.id,
        TenantMembership.user_id == user.id
    )
    membership = db.execute(stmt).scalar_one_or_none()
    if not membership:
        add_tenant_membership(db, tenant.id, user.id, role='OWNER')
    
    return user, tenant
