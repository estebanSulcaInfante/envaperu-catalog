from flask import Blueprint, request, jsonify, abort
import sqlalchemy as sa
from ...models import db, Catalogo, CatalogoSesion, CatalogoSesionVersion
from ...decorators import require_auth

versiones_bp = Blueprint("versiones", __name__, url_prefix="/versiones")


def _num(x):
    return float(x) if x is not None else None


def _version_to_json(v: CatalogoSesionVersion) -> dict:
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
        # derivados útiles
        "precio_x_docena": _num(getattr(v, "precio_x_docena", None)),
        "precio_unidad_exw": _num(getattr(v, "precio_unidad_exw", None)),
        "subtotal_exw": _num(getattr(v, "subtotal_exw", None)),
        "volumen_paquete_cbm": _num(getattr(v, "volumen_paquete_cbm", None)),
        "cbm_total": _num(getattr(v, "cbm_total", None)),
        "cantidad_por_paquete": _num(getattr(v, "cantidad_por_paquete", None)),
        "cantidad_unidades": _num(getattr(v, "cantidad_unidades", None)),
        "peso_neto_kg": _num(getattr(v, "peso_neto_kg", None)),
        "peso_bruto_kg": _num(getattr(v, "peso_bruto_kg", None)),
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _get_version_or_404(version_id: int) -> CatalogoSesionVersion:
    v = db.session.get(CatalogoSesionVersion, int(version_id))
    if not v:
        abort(404, description="versión no existe")
    return v


@versiones_bp.post("/sesiones/<int:sesion_id>")
@require_auth
def crear_version(sesion_id: int):
    s = db.session.get(CatalogoSesion, sesion_id)
    if not s:
        abort(404, description="sesión no existe")

    c = db.session.get(Catalogo, s.catalogo_id)
    if not c:
        abort(404, description="catálogo no existe")
    if c.estado != "EN_PROCESO":
        return jsonify({"error": "catálogo no admite nuevas versiones"}), 409

    # último número de versión (sin FOR SHARE)
    last_num = db.session.scalar(
        sa.select(CatalogoSesionVersion.version_num)
        .where(
            CatalogoSesionVersion.sesion_id == s.id,
            CatalogoSesionVersion.catalogo_id == c.id,
        )
        .order_by(CatalogoSesionVersion.version_num.desc())
        .limit(1)
    ) or 0
    next_num = int(last_num) + 1

    # anular current previo de la sesión
    db.session.execute(
        sa.update(CatalogoSesionVersion)
        .where(CatalogoSesionVersion.sesion_id == s.id)
        .values(is_current=False)
    )

    # snapshot desde producto + overrides
    prod = c.producto
    body = request.get_json(silent=True) or {}

    v = CatalogoSesionVersion(
        sesion_id=s.id,
        catalogo_id=c.id,
        producto_id=prod.id,
        version_num=next_num,
        estado="BORRADOR",
        is_current=True,
        is_final=False,
        um=body.get("um", prod.um),
        doc_x_bulto_caja=body.get("doc_x_bulto_caja", prod.doc_x_bulto_caja),
        doc_x_paq=body.get("doc_x_paq", prod.doc_x_paq),
        precio_exw=body.get("precio_exw", prod.precio_exw),
        familia=body.get("familia", prod.familia),
        foto_key=body.get("foto_key", prod.imagen_key),
        cant_bultos=body.get("cant_bultos", 0),
        porc_desc=body.get("porc_desc"),
        observaciones=body.get("observaciones"),
        peso_gr=body.get("peso_gr"),
        largo_cm=body.get("largo_cm"),
        ancho_cm=body.get("ancho_cm"),
        alto_cm=body.get("alto_cm"),
    )

    db.session.add(v)
    db.session.commit()
    return jsonify(_version_to_json(v)), 201


@versiones_bp.get("/<int:version_id>")
@require_auth
def obtener_version(version_id: int):
    v = _get_version_or_404(version_id)
    return jsonify(_version_to_json(v))


@versiones_bp.patch("/<int:version_id>")
@require_auth
def editar_version(version_id: int):
    v = _get_version_or_404(version_id)
    c = db.session.get(Catalogo, v.catalogo_id)
    if not c or c.estado != "EN_PROCESO":
        return jsonify({"error": "catálogo no editable"}), 409

    if v.estado not in ("BORRADOR", "ENVIADA", "CONTRAOFERTA"):
        return jsonify({"error": "versión no editable en este estado"}), 409

    body = request.get_json(silent=True) or {}
    for f in (
        "um", "doc_x_bulto_caja", "doc_x_paq", "precio_exw", "porc_desc",
        "cant_bultos", "peso_gr", "largo_cm", "ancho_cm", "alto_cm",
        "familia", "foto_key", "observaciones"
    ):
        if f in body:
            setattr(v, f, body[f])

    db.session.commit()
    return jsonify(_version_to_json(v))


def _set_estado(v: CatalogoSesionVersion, nuevo: str):
    v.estado = nuevo
    db.session.commit()
    return jsonify(_version_to_json(v))


@versiones_bp.post("/<int:version_id>/enviar")
@require_auth
def enviar_version(version_id: int):
    v = _get_version_or_404(version_id)
    if v.estado != "BORRADOR":
        return jsonify({"error": "solo BORRADOR puede ENVIARSE"}), 409
    return _set_estado(v, "ENVIADA")


@versiones_bp.post("/<int:version_id>/contraoferta")
@require_auth
def contraoferta_version(version_id: int):
    v = _get_version_or_404(version_id)
    if v.estado != "ENVIADA":
        return jsonify({"error": "solo ENVIADA puede pasar a CONTRAOFERTA"}), 409
    return _set_estado(v, "CONTRAOFERTA")


@versiones_bp.post("/<int:version_id>/rechazar")
@require_auth
def rechazar_version(version_id: int):
    v = _get_version_or_404(version_id)
    if v.estado not in ("ENVIADA", "CONTRAOFERTA"):
        return jsonify({"error": "solo ENVIADA/CONTRAOFERTA puede RECHAZARSE"}), 409
    return _set_estado(v, "RECHAZADA")


@versiones_bp.post("/<int:version_id>/aprobar")
@require_auth
def aprobar_version(version_id: int):
    v = _get_version_or_404(version_id)
    if v.estado not in ("ENVIADA", "CONTRAOFERTA"):
        return jsonify({"error": "solo ENVIADA/CONTRAOFERTA puede APROBARSE"}), 409

    # marcar final y cerrar catálogo
    v.estado = "APROBADA"
    v.is_final = True
    # asegurar current sobre esta versión
    db.session.execute(
        sa.update(CatalogoSesionVersion)
        .where(CatalogoSesionVersion.sesion_id == v.sesion_id)
        .values(is_current=False)
    )
    v.is_current = True

    c = db.session.get(Catalogo, v.catalogo_id)
    c.final_version_id = v.id
    c.estado = "CERRADA"

    db.session.commit()
    return jsonify(_version_to_json(v))


@versiones_bp.post("/<int:version_id>/current")
@require_auth
def forzar_current(version_id: int):
    v = _get_version_or_404(version_id)
    if v.is_final:
        return jsonify({"error": "no se puede marcar current una versión final"}), 409

    db.session.execute(
        sa.update(CatalogoSesionVersion)
        .where(CatalogoSesionVersion.sesion_id == v.sesion_id)
        .values(is_current=False)
    )
    v.is_current = True
    db.session.commit()
    return jsonify(_version_to_json(v))
