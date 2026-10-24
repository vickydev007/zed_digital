from __future__ import annotations
import os
import base64
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from cryptography.fernet import Fernet
from backend.core.config import settings

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire, 'iat': now})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except Exception:
        return None

def get_fernet_cipher() -> Fernet:
    key_str = settings.ENCRYPTION_KEY
    try:
        raw_key = base64.urlsafe_b64decode(key_str.encode('utf-8'))
        if len(raw_key) != 32:
            padded = (raw_key + b'0' * 32)[:32]
            key_str = base64.urlsafe_b64encode(padded).decode('utf-8')
    except Exception:
        key_str = Fernet.generate_key().decode('utf-8')
    return Fernet(key_str.encode('utf-8') if isinstance(key_str, str) else key_str)

def encrypt_secret(secret_text: str) -> str:
    cipher = get_fernet_cipher()
    return cipher.encrypt(secret_text.encode('utf-8')).decode('utf-8')

def decrypt_secret(cipher_text: str) -> str:
    try:
        cipher = get_fernet_cipher()
        return cipher.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except Exception:
        return ''
