import time, secrets, hashlib
import jwt
from passlib.hash import argon2
from datetime import datetime, timezone, timedelta
from flask import current_app

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

# -------- Password hashing --------
def hash_pwd(p: str) -> str:
    return argon2.hash(p)

def verify_pwd(p: str, h: str) -> bool:
    try:
        return argon2.verify(p, h)
    except Exception:
        return False

# -------- Access JWT (corto) --------
def make_access_token(user_id: int, email: str, roles: list[str]) -> str:
    cfg = current_app.config
    iat = int(time.time())
    exp = iat + cfg["ACCESS_TTL_MIN"] * 60
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "typ": "access",
        "iat": iat,
        "exp": exp,
    }
    return jwt.encode(payload, cfg["JWT_SECRET"], algorithm=cfg["JWT_ALG"])

def decode_access_token(token: str) -> dict:
    cfg = current_app.config
    return jwt.decode(token, cfg["JWT_SECRET"], algorithms=[cfg["JWT_ALG"]])

# -------- Refresh token (opaco, almacenado en BD como hash) --------
def new_refresh_token() -> str:
    # token opaco seguro
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def is_refresh_expired(created_at: datetime) -> bool:
    ttl_days = current_app.config["REFRESH_TTL_D"]
    return created_at + timedelta(days=ttl_days) < now_utc()