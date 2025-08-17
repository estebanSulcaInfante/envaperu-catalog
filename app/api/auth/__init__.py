# app/api/auth/__init__.py
from flask import Blueprint, request, jsonify, abort
from sqlalchemy import func
from ...models import db, Usuario, RefreshToken, Rol  # usa tus modelos
from ...security import (
    hash_pwd, verify_pwd,
    make_access_token, new_refresh_token, hash_refresh_token,
    is_refresh_expired, now_utc
)
from ...decorators import require_auth
import pyotp

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ---------- helpers ----------
def normalize_email(email: str) -> str:
    return (email or "").strip()

def user_roles(u: Usuario) -> list[str]:
    return [r.nombre for r in (u.roles or [])]

def client_fingerprint():
    ua = request.headers.get("User-Agent", "")[:300]
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return ua, ip

# ---------- seed/registro ----------
@auth_bp.post("/register")
def register():
    """
    Crea el primer usuario si no existe ninguno.
    Para crear más usuarios, luego crea un endpoint protegido por rol ADMIN.
    """
    total = db.session.scalar(db.select(func.count(Usuario.id)))
    if total and total > 0:
        abort(403, description="registro deshabilitado (ya existe usuario)")

    data = request.get_json() or {}
    email = normalize_email(data.get("email"))
    password = data.get("password")
    nombre = data.get("nombre") or email

    if not email or not password:
        abort(400, description="email y password son requeridos")

    # Unique case-insensitive
    exists = db.session.scalar(
        db.select(Usuario.id).where(func.lower(Usuario.email) == func.lower(email))
    )
    if exists:
        abort(409, description="email ya registrado")

    u = Usuario(email=email, pass_hash=hash_pwd(password), nombre=nombre, estado="ACTIVO")
    db.session.add(u)
    db.session.commit()

    # (opcional) asignar rol ADMIN si tienes roles precargados
    # admin = db.session.scalar(db.select(Rol).where(Rol.nombre == "ADMIN"))
    # if admin:
    #     u.roles.append(admin); db.session.commit()

    return jsonify({"id": u.id, "email": u.email}), 201

# ---------- login ----------
@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    email = normalize_email(data.get("email"))
    password = data.get("password")
    totp_code = (data.get("totp") or "").replace(" ", "")

    if not email or not password:
        abort(400, description="email y password son requeridos")

    u: Usuario | None = db.session.scalar(
        db.select(Usuario).where(func.lower(Usuario.email) == func.lower(email))
    )
    if not u or u.estado != "ACTIVO" or not verify_pwd(password, u.pass_hash):
        abort(401, description="credenciales inválidas")

    # Si el usuario tiene MFA, requiere TOTP válido
    if u.mfa_totp_secret:
        if not totp_code:
            return jsonify({"mfa_required": True}), 401
        totp = pyotp.TOTP(u.mfa_totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            abort(401, description="código MFA inválido")

    roles = user_roles(u)

    # Access JWT
    access = make_access_token(u.id, u.email, roles)

    # Refresh opaco (rotativo)
    raw_refresh = new_refresh_token()
    hashed = hash_refresh_token(raw_refresh)
    ua, ip = client_fingerprint()
    rt = RefreshToken(usuario_id=u.id, token_hash=hashed, user_agent=ua, ip=ip)
    db.session.add(rt)
    u.last_login_at = now_utc()
    db.session.commit()

    return jsonify({
        "access_token": access,
        "refresh_token": raw_refresh,
        "user": {"id": u.id, "email": u.email, "nombre": u.nombre, "roles": roles}
    }), 200

# ---------- refresh (rotación obligatoria) ----------
@auth_bp.post("/refresh")
def refresh():
    data = request.get_json() or {}
    raw = data.get("refresh_token")
    if not raw:
        abort(400, description="refresh_token requerido")

    hashed = hash_refresh_token(raw)
    rt: RefreshToken | None = db.session.scalar(
        db.select(RefreshToken).where(RefreshToken.token_hash == hashed)
    )
    if not rt or rt.revoked_at is not None:
        abort(401, description="refresh inválido")

    if is_refresh_expired(rt.created_at):
        # revoca por expiración
        rt.revoked_at = now_utc()
        db.session.commit()
        abort(401, description="refresh expirado")

    # Carga usuario
    u: Usuario | None = db.session.get(Usuario, rt.usuario_id)
    if not u or u.estado != "ACTIVO":
        abort(401, description="usuario inactivo")

    roles = user_roles(u)
    access = make_access_token(u.id, u.email, roles)

    # Rotación: revoca el actual y crea uno nuevo
    rt.revoked_at = now_utc()
    raw_new = new_refresh_token()
    hashed_new = hash_refresh_token(raw_new)
    ua, ip = client_fingerprint()
    rt2 = RefreshToken(usuario_id=u.id, token_hash=hashed_new, user_agent=ua, ip=ip)
    db.session.add(rt2)
    db.session.commit()

    return jsonify({"access_token": access, "refresh_token": raw_new}), 200

# ---------- logout (revoca refresh) ----------
@auth_bp.post("/logout")
def logout():
    data = request.get_json() or {}
    raw = data.get("refresh_token")
    if not raw:
        abort(400, description="refresh_token requerido")
    hashed = hash_refresh_token(raw)
    rt: RefreshToken | None = db.session.scalar(
        db.select(RefreshToken).where(RefreshToken.token_hash == hashed)
    )
    if rt and rt.revoked_at is None:
        rt.revoked_at = now_utc()
        db.session.commit()
    return jsonify({"ok": True}), 200

# ---------- whoami ----------
@auth_bp.get("/whoami")
@require_auth
def whoami():
    p = getattr(request, "user", {})
    return jsonify(p), 200

# ---------- MFA: setup/enable/disable ----------
@auth_bp.post("/mfa/setup")
@require_auth
def mfa_setup():
    """Genera un secreto TOTP y URI para QR (el cliente muestra el QR).
       Por simplicidad, el secreto se devuelve al cliente; en producción,
       podrías almacenarlo temporalmente del lado servidor.
    """
    data = request.get_json() or {}
    issuer = data.get("issuer") or "MiEmpresa"
    user_email = request.user.get("email")
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=issuer)
    return jsonify({"secret": secret, "otpauth_uri": uri}), 200

@auth_bp.post("/mfa/enable")
@require_auth
def mfa_enable():
    """Activa MFA guardando el secreto si el código es válido."""
    data = request.get_json() or {}
    secret = data.get("secret")
    code = (data.get("code") or "").replace(" ", "")
    if not secret or not code:
        abort(400, description="secret y code requeridos")

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        abort(401, description="código inválido")

    uid = int(request.user["sub"])
    u: Usuario | None = db.session.get(Usuario, uid)
    if not u or u.estado != "ACTIVO":
        abort(401)
    u.mfa_totp_secret = secret
    db.session.commit()
    return jsonify({"mfa_enabled": True}), 200

@auth_bp.post("/mfa/disable")
@require_auth
def mfa_disable():
    """Desactiva MFA. Opcionalmente podrías pedir el código actual."""
    uid = int(request.user["sub"])
    u: Usuario | None = db.session.get(Usuario, uid)
    if not u:
        abort(401)
    u.mfa_totp_secret = None
    db.session.commit()
    return jsonify({"mfa_enabled": False}), 200
