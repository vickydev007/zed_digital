from __future__ import annotations
import os
from typing import Generator
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.dialects.postgresql import JSONB
from backend.core.config import settings

def get_engine_url() -> str:
    url = settings.DATABASE_URL
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    return url

db_url = get_engine_url()

if db_url.startswith('sqlite'):
    engine = create_engine(db_url, connect_args={'check_same_thread': False})
    
    @event.listens_for(engine, 'connect')
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON;')
        cursor.close()
else:
    engine = create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

CompatibleJSON = JSON().with_variant(JSONB, 'postgresql')

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
