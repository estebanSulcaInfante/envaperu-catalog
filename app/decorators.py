from functools import wraps
from flask import request, abort, make_response
from .security import decode_access_token

def require_auth(fn):
    @wraps(fn)
    def _w(*args, **kwargs):
        # Nunca exigir autenticación en pre-flight CORS
        if request.method == "OPTIONS":
            # Flask-CORS añadirá las cabeceras necesarias
            return make_response(("", 204))

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            abort(401)
        token = auth.split()[1]
        try:
            payload = decode_access_token(token)
        except Exception:
            abort(401)

        # Guarda el payload del token para que el handler lo use si lo necesita
        request.user = payload  # {"sub": "...", "email": "...", "roles": [...]}
        return fn(*args, **kwargs)
    return _w
