from flask import Blueprint, request, jsonify, abort
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from ...models import db, Catalogo, CatalogoSesion, CatalogoSesionVersion
from ...decorators import require_auth

sesiones_bp = Blueprint("sesiones", __name__, url_prefix="/sesiones")


def _num(x):
    return float(x) if x is not None else None


def _serialize_version_min(v: CatalogoSesionVersion | None) -> dict | None:
    if not v:
        return None
    return {
        "id": v.id,
        "version_num": v.version_num,
        "estado": v.estado,
        "is_current": v.is_current,
        "is_final": v.is_final,
        "precio_exw": _num(v.precio_exw),
        "porc_desc": _num(v.porc_desc),
        "subtotal_exw": _num(v.subtotal_exw),
    }


def serialize_sesion(s: CatalogoSesion, current: CatalogoSesionVersion | None = None) -> dict:
    return {
        "id": s.id,
        "catalogo_id": s.catalogo_id,
        "etiqueta": s.etiqueta,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "current_version": _serialize_version_min(current) if current else None,
    }


def _get_catalogo_or_404(catalogo_id: int) -> Catalogo:
    c = db.session.get(Catalogo, int(catalogo_id))
    if not c:
        abort(404, description="catálogo no existe")
    return c


def _catalogo_editable(c: Catalogo):
    if c.estado != "EN_PROCESO":
        abort(409, description="catálogo no editable (estado != EN_PROCESO)")


def _paginated(q):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        abort(400, description="page/per_page inválidos")
    per_page = max(1, min(per_page, 100))
    items = q.limit(per_page).offset((page-1)*per_page).all()
    return items, page, per_page

# ---------------------------
# GET /api/catalogos/{catalogo_id}/sesiones
# ---------------------------
@sesiones_bp.get("/catalogos/<int:catalogo_id>")
@require_auth
def listar_sesiones(catalogo_id: int):
    c = _get_catalogo_or_404(catalogo_id)

    q = CatalogoSesion.query.filter(CatalogoSesion.catalogo_id == c.id)
    is_active = request.args.get("is_active")
    if is_active is not None:
        flag = is_active.lower() in ("1", "true", "yes", "y")
        q = q.filter(CatalogoSesion.is_active == flag)

    q = q.order_by(CatalogoSesion.created_at.desc(), CatalogoSesion.id.desc())
    items, page, per_page = _paginated(q)

    # with_current=true para adjuntar versión vigente de cada sesión
    with_current = (request.args.get("with_current") or "").lower() in ("1", "true", "yes", "y")

    data = []
    if with_current:
        for s in items:
            current = db.session.scalar(
                db.select(CatalogoSesionVersion)
                .where(
                    CatalogoSesionVersion.sesion_id == s.id,
                    CatalogoSesionVersion.catalogo_id == s.catalogo_id,
                    CatalogoSesionVersion.is_current.is_(True),
                )
                .order_by(CatalogoSesionVersion.version_num.desc())
                .limit(1)
            )
            data.append(serialize_sesion(s, current))
    else:
        data = [serialize_sesion(s) for s in items]

    return jsonify({"data": data, "page": page, "per_page": per_page})

# ---------------------------
# POST /api/catalogos/{catalogo_id}/sesiones
# ---------------------------
@sesiones_bp.post("/catalogos/<int:catalogo_id>")
@require_auth
def crear_sesion(catalogo_id: int):
    c = _get_catalogo_or_404(catalogo_id)
    _catalogo_editable(c)

    data = request.get_json() or {}
    etiqueta = (data.get("etiqueta") or "escenario").strip()

    s = CatalogoSesion(catalogo_id=c.id, etiqueta=etiqueta, is_active=True)
    db.session.add(s)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad al crear sesión")

    return jsonify(serialize_sesion(s)), 201

# ---------------------------
# GET /api/sesiones/{sesion_id}
# ---------------------------
@sesiones_bp.get("/<int:sesion_id>")
@require_auth
def obtener_sesion(sesion_id: int):
    s = db.session.get(CatalogoSesion, sesion_id)
    if not s:
        abort(404)

    # with_current=true para traer también la versión vigente
    with_current = (request.args.get("with_current") or "").lower() in ("1", "true", "yes", "y")
    current = None
    if with_current:
        current = db.session.scalar(
            db.select(CatalogoSesionVersion)
            .where(
                CatalogoSesionVersion.sesion_id == s.id,
                CatalogoSesionVersion.catalogo_id == s.catalogo_id,
                CatalogoSesionVersion.is_current.is_(True),
            )
            .order_by(CatalogoSesionVersion.version_num.desc())
            .limit(1)
        )
    return jsonify(serialize_sesion(s, current))

# ---------------------------
# PATCH /api/sesiones/{sesion_id}
# ---------------------------
@sesiones_bp.patch("/<int:sesion_id>")
@require_auth
def editar_sesion(sesion_id: int):
    s = db.session.get(CatalogoSesion, sesion_id)
    if not s:
        abort(404)

    c = _get_catalogo_or_404(s.catalogo_id)
    _catalogo_editable(c)

    data = request.get_json() or {}
    if "etiqueta" in data:
        s.etiqueta = (data.get("etiqueta") or s.etiqueta or "").strip()
    if "is_active" in data:
        s.is_active = bool(data.get("is_active"))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad al editar sesión")

    return jsonify(serialize_sesion(s))

# ---------------------------
# DELETE /api/sesiones/{sesion_id}
# ---------------------------
@sesiones_bp.delete("/<int:sesion_id>")
@require_auth
def eliminar_sesion(sesion_id: int):
    s = db.session.get(CatalogoSesion, sesion_id)
    if not s:
        abort(404)

    c = _get_catalogo_or_404(s.catalogo_id)
    _catalogo_editable(c)

    # ¿Tiene versiones? Si tiene, no permitimos borrar para preservar histórico.
    count_versions = db.session.scalar(
        db.select(func.count(CatalogoSesionVersion.id))
        .where(
            CatalogoSesionVersion.sesion_id == s.id,
            CatalogoSesionVersion.catalogo_id == s.catalogo_id,
        )
    )
    if count_versions and count_versions > 0:
        abort(409, description="no se puede borrar: la sesión tiene versiones")

    db.session.delete(s)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error al eliminar sesión")

    return jsonify({"ok": True})
