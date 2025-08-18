from flask import Blueprint, request, jsonify, abort
from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError
from ...models import (
    db, Catalogo, CatalogoSesion, CatalogoSesionVersion, Producto
)
from ...decorators import require_auth

versiones_bp = Blueprint("versiones", __name__, url_prefix="/versiones")

ESTADOS_EDITABLES = {"BORRADOR", "ENVIADA"}

def _num(x): return float(x) if x is not None else None

def serialize_version(v: CatalogoSesionVersion) -> dict:
    return {
        "id": v.id,
        "sesion_id": v.sesion_id,
        "catalogo_id": v.catalogo_id,
        "producto_id": v.producto_id,
        "version_num": v.version_num,
        "estado": v.estado,
        "is_current": v.is_current,
        "is_final": v.is_final,
        "um": v.um,
        "doc_x_bulto_caja": _num(v.doc_x_bulto_caja),
        "doc_x_paq": _num(v.doc_x_paq),
        "precio_exw": _num(v.precio_exw),
        "porc_desc": _num(v.porc_desc),
        "cant_bultos": _num(v.cant_bultos),
        "peso_gr": _num(v.peso_gr),
        "largo_cm": _num(v.largo_cm),
        "ancho_cm": _num(v.ancho_cm),
        "alto_cm": _num(v.alto_cm),
        "familia": v.familia,
        "foto_key": v.foto_key,
        "observaciones": v.observaciones,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        # calculados
        "precio_x_docena": _num(v.precio_x_docena),
        "cantidad_por_paquete": _num(v.cantidad_por_paquete),
        "precio_unidad_exw": _num(v.precio_unidad_exw),
        "volumen_paquete_cbm": _num(v.volumen_paquete_cbm),
        "cantidad_unidades": _num(v.cantidad_unidades),
        "subtotal_exw": _num(v.subtotal_exw),
        "cbm_total": _num(v.cbm_total),
        "peso_neto_kg": _num(v.peso_neto_kg),
        "peso_bruto_kg": _num(v.peso_bruto_kg),
    }

def _get_sesion_or_404(sid: int) -> CatalogoSesion:
    s = db.session.get(CatalogoSesion, sid)
    if not s: abort(404, description="sesión no existe")
    return s

def _get_catalogo_or_404(cid: int) -> Catalogo:
    c = db.session.get(Catalogo, cid)
    if not c: abort(404, description="catálogo no existe")
    return c

def _catalogo_editable(c: Catalogo):
    if c.estado != "EN_PROCESO":
        abort(409, description="catálogo no editable (estado != EN_PROCESO)")

def _require_editable_version(v: CatalogoSesionVersion):
    if v.estado not in ESTADOS_EDITABLES:
        abort(409, description=f"versión no editable en estado {v.estado}")

def _paginated(q):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        abort(400, description="page/per_page inválidos")
    per_page = max(1, min(per_page, 100))
    items = q.limit(per_page).offset((page-1)*per_page).all()
    return items, page, per_page

# -------------------------------------------
# GET /api/sesiones/{sesion_id}/versiones
# -------------------------------------------
@versiones_bp.get("/sesiones/<int:sesion_id>")
@require_auth
def listar_por_sesion(sesion_id: int):
    s = _get_sesion_or_404(sesion_id)
    q = CatalogoSesionVersion.query.filter(
        CatalogoSesionVersion.sesion_id == s.id,
        CatalogoSesionVersion.catalogo_id == s.catalogo_id
    )
    # filtros
    estado = request.args.get("estado")
    is_current = request.args.get("is_current")
    if estado:
        q = q.filter(CatalogoSesionVersion.estado == estado)
    if is_current is not None:
        flag = is_current.lower() in ("1","true","yes","y")
        q = q.filter(CatalogoSesionVersion.is_current.is_(flag))

    q = q.order_by(CatalogoSesionVersion.version_num.desc())
    items, page, per_page = _paginated(q)
    return jsonify({
        "data": [serialize_version(i) for i in items],
        "page": page, "per_page": per_page
    })

# -------------------------------------------
# POST /api/sesiones/{sesion_id}/versiones  (crear snapshot)
# -------------------------------------------
@versiones_bp.post("/sesiones/<int:sesion_id>")
@require_auth
def crear_version(sesion_id: int):
    s = _get_sesion_or_404(sesion_id)
    c = _get_catalogo_or_404(s.catalogo_id)
    _catalogo_editable(c)

    # No crear si ya hay final en el catálogo
    if c.final_version_id:
        abort(409, description="catálogo con versión final: no se pueden crear nuevas versiones")

    # Producto maestro
    p = db.session.get(Producto, c.producto_id)
    if not p:
        abort(400, description="producto no existe")

    data = request.get_json() or {}

    # Calcular siguiente version_num y apagar current anterior (transacción)
    try:
        with db.session.begin_nested():
            # lock versiones de la sesión para evitar carreras
            prev_current = db.session.scalar(
                select(CatalogoSesionVersion)
                .where(
                    CatalogoSesionVersion.sesion_id == s.id,
                    CatalogoSesionVersion.catalogo_id == s.catalogo_id,
                    CatalogoSesionVersion.is_current.is_(True),
                )
                .with_for_update(read=True, nowait=False, of=CatalogoSesionVersion)
            )
            max_ver = db.session.scalar(
                select(func.coalesce(func.max(CatalogoSesionVersion.version_num), 0))
                .where(
                    CatalogoSesionVersion.sesion_id == s.id,
                    CatalogoSesionVersion.catalogo_id == s.catalogo_id,
                )
                .with_for_update(read=True, nowait=False, of=CatalogoSesionVersion)
            )
            next_num = int(max_ver) + 1

            v = CatalogoSesionVersion(
                sesion_id=s.id,
                catalogo_id=s.catalogo_id,
                producto_id=c.producto_id,
                version_num=next_num,
                estado="BORRADOR",
                is_current=True,
                is_final=False,
                # snapshot desde Producto (permitiendo overrides del body)
                um = data.get("um") or p.um,
                doc_x_bulto_caja = data.get("doc_x_bulto_caja", p.doc_x_bulto_caja),
                doc_x_paq = data.get("doc_x_paq", p.doc_x_paq),
                precio_exw = data.get("precio_exw", p.precio_exw),
                porc_desc  = data.get("porc_desc"),
                cant_bultos= data.get("cant_bultos", 0),
                peso_gr    = data.get("peso_gr"),
                largo_cm   = data.get("largo_cm"),
                ancho_cm   = data.get("ancho_cm"),
                alto_cm    = data.get("alto_cm"),
                familia    = data.get("familia", p.familia),
                foto_key   = data.get("foto_key", p.imagen_key),
                observaciones = data.get("observaciones"),
            )
            if v.doc_x_paq is None:
                abort(400, description="doc_x_paq requerido (no viene en producto ni en body)")
            if v.precio_exw is None:
                abort(400, description="precio_exw requerido (no viene en producto ni en body)")

            db.session.add(v)
            if prev_current:
                prev_current.is_current = False

        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad creando versión")

    return jsonify(serialize_version(v)), 201

# -------------------------------------------
# GET /api/versiones/{id}
# -------------------------------------------
@versiones_bp.get("/<int:version_id>")
@require_auth
def obtener_version(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    return jsonify(serialize_version(v))

# -------------------------------------------
# PATCH /api/versiones/{id}  (editar campos si editable)
# -------------------------------------------
@versiones_bp.patch("/<int:version_id>")
@require_auth
def editar_version(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)
    _require_editable_version(v)

    data = request.get_json() or {}
    # Permitimos editar snapshot y términos
    for k in ["um","doc_x_bulto_caja","doc_x_paq","precio_exw","porc_desc",
              "cant_bultos","peso_gr","largo_cm","ancho_cm","alto_cm",
              "familia","foto_key","observaciones"]:
        if k in data:
            setattr(v, k, data[k])

    if v.doc_x_paq is None or v.precio_exw is None:
        abort(400, description="doc_x_paq y precio_exw no pueden ser nulos")

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad al editar versión")

    return jsonify(serialize_version(v))

# -------------------------------------------
# POST /api/versiones/{id}/enviar
# -------------------------------------------
@versiones_bp.post("/<int:version_id>/enviar")
@require_auth
def enviar(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)
    if v.estado not in {"BORRADOR","CONTRAOFERTA"}:
        abort(409, description=f"no se puede ENVIAR desde {v.estado}")
    v.estado = "ENVIADA"
    db.session.commit()
    return jsonify(serialize_version(v))

# -------------------------------------------
# POST /api/versiones/{id}/contraoferta
# -------------------------------------------
@versiones_bp.post("/<int:version_id>/contraoferta")
@require_auth
def contraoferta(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)
    if v.estado not in {"ENVIADA"}:
        abort(409, description=f"no se puede pasar a CONTRAOFERTA desde {v.estado}")
    v.estado = "CONTRAOFERTA"
    db.session.commit()
    return jsonify(serialize_version(v))

# -------------------------------------------
# POST /api/versiones/{id}/rechazar
# -------------------------------------------
@versiones_bp.post("/<int:version_id>/rechazar")
@require_auth
def rechazar(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)
    if v.estado not in {"ENVIADA","CONTRAOFERTA"}:
        abort(409, description=f"no se puede RECHAZAR desde {v.estado}")
    v.estado = "RECHAZADA"
    db.session.commit()
    return jsonify(serialize_version(v))

# -------------------------------------------
# POST /api/versiones/{id}/aprobar  (marca final y cierra catálogo)
# -------------------------------------------
@versiones_bp.post("/<int:version_id>/aprobar")
@require_auth
def aprobar(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)

    # Solo desde ENVIADA o CONTRAOFERTA (ajusta si quieres permitir otras)
    if v.estado not in {"ENVIADA","CONTRAOFERTA"}:
        abort(409, description=f"no se puede APROBAR desde {v.estado}")

    # Verifica que no exista otra final en el catálogo
    ya_final = db.session.scalar(
        select(func.count(CatalogoSesionVersion.id)).where(
            CatalogoSesionVersion.catalogo_id == c.id,
            CatalogoSesionVersion.is_final.is_(True)
        )
    )
    if ya_final and ya_final > 0:
        abort(409, description="el catálogo ya tiene una versión final")

    try:
        with db.session.begin_nested():
            v.estado = "APROBADA"
            v.is_final = True
            # Marca final en catálogo y cierra
            c.final_version_id = v.id
            c.estado = "CERRADA"
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description="conflicto: ya existe final en el catálogo")

    return jsonify(serialize_version(v))

# -------------------------------------------
# POST /api/versiones/{id}/current  (forzar vigente en la sesión)
# -------------------------------------------
@versiones_bp.post("/<int:version_id>/current")
@require_auth
def hacer_current(version_id: int):
    v = db.session.get(CatalogoSesionVersion, version_id)
    if not v: abort(404)
    c = _get_catalogo_or_404(v.catalogo_id)
    _catalogo_editable(c)
    if v.is_final:
        abort(409, description="una versión final no puede ser currentizada")

    try:
        with db.session.begin_nested():
            prev_current = db.session.scalar(
                select(CatalogoSesionVersion).where(
                    CatalogoSesionVersion.sesion_id == v.sesion_id,
                    CatalogoSesionVersion.catalogo_id == v.catalogo_id,
                    CatalogoSesionVersion.is_current.is_(True),
                    CatalogoSesionVersion.id != v.id,
                ).with_for_update()
            )
            if prev_current:
                prev_current.is_current = False
            v.is_current = True
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error al establecer current")

    return jsonify(serialize_version(v))
