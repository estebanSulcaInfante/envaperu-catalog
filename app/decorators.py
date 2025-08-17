from functools import wraps
from flask import request, abort
from .security import decode_access_token

def require_auth(fn):
    @wraps(fn)
    def _w(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            abort(401)
        token = auth.split()[1]
        try:
            payload = decode_access_token(token)
        except Exception:
            abort(401)
        request.user = payload  # {"sub": "...", "email": "...", "roles": [...]}
        return fn(*args, **kwargs)
    return _w
