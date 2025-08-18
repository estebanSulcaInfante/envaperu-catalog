# app/api/catalogo/__init__.py
from flask import Blueprint, request, jsonify, abort
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from ...models import (
    db, Catalogo, CatalogoSesion, CatalogoSesionVersion,
    Cliente, Producto
)
from ...decorators import require_auth

catalogo_bp = Blueprint("catalogo", __name__, url_prefix="/catalogos")

ESTADOS_CATALOGO = {"EN_PROCESO", "CERRADA", "CANCELADA"}

def _num(x):
    return float(x) if x is not None else None

def serialize_version(v: CatalogoSesionVersion) -> dict:
    if not v:
        return None
    return {
        "id": v.id,
        "sesion_id": v.sesion_id,
        "catalogo_id": v.catalogo_id,
        "producto_id": v.producto_id,
        "version_num": v.version_num,
        "estado": v.estado,
        "is_current": v.is_current,
        "is_final": v.is_final,
        # snapshot
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
        # calculados (column_property en BD)
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

def serialize_catalogo(c: Catalogo) -> dict:
    return {
        "id": c.id,
        "cliente_id": c.cliente_id,
        "producto_id": c.producto_id,
        "estado": c.estado,
        "final_version_id": c.final_version_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        # opcionalmente, nombres para UI:
        "cliente_nombre": c.cliente.nombre if c.cliente else None,
        "producto_nombre": c.producto.nombre if c.producto else None,
        # y si quieres devolver un resumen de la final:
        "final_version": serialize_version(c.final_version) if c.final_version else None,
    }

def _paginated(q):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        abort(400, description="page/per_page inválidos")
    per_page = max(1, min(per_page, 100))
    items = q.limit(per_page).offset((page-1)*per_page).all()
    return items, page, per_page

@catalogo_bp.get("")
@require_auth
def listar_catalogos():
    q = Catalogo.query.join(Cliente, Catalogo.cliente_id == Cliente.id) \
                      .join(Producto, Catalogo.producto_id == Producto.id)

    # filtros
    cliente_id = request.args.get("cliente_id")
    producto_id = request.args.get("producto_id")
    estado = request.args.get("estado")
    with_final = request.args.get("with_final")

    if cliente_id:
        q = q.filter(Catalogo.cliente_id == int(cliente_id))
    if producto_id:
        q = q.filter(Catalogo.producto_id == int(producto_id))
    if estado:
        if estado not in ESTADOS_CATALOGO:
            abort(400, description="estado inválido")
        q = q.filter(Catalogo.estado == estado)
    if with_final is not None:
        # ?with_final=true|false
        flag = with_final.lower() in ("1", "true", "yes", "y")
        if flag:
            q = q.filter(Catalogo.final_version_id.isnot(None))
        else:
            q = q.filter(Catalogo.final_version_id.is_(None))

    # búsqueda por nombre de cliente o producto
    search = (request.args.get("search") or "").strip().lower()
    if search:
        like = f"%{search}%"
        q = q.filter(
            func.lower(Cliente.nombre).like(like) |
            func.lower(Producto.nombre).like(like)
        )

    q = q.order_by(Catalogo.created_at.desc(), Catalogo.id.desc())
    items, page, per_page = _paginated(q)
    return jsonify({
        "data": [serialize_catalogo(i) for i in items],
        "page": page, "per_page": per_page
    })

@catalogo_bp.post("")
@require_auth
def crear_catalogo():
    """
    Crea un catálogo (único por cliente_id + producto_id).
    Crea automáticamente una sesión inicial (etiqueta opcional).
    """
    data = request.get_json() or {}
    cliente_id = data.get("cliente_id")
    producto_id = data.get("producto_id")
    etiqueta = (data.get("etiqueta") or "default").strip()

    if not cliente_id or not producto_id:
        abort(400, description="cliente_id y producto_id son requeridos")

    # existen?
    if not db.session.get(Cliente, int(cliente_id)):
        abort(400, description="cliente no existe")
    if not db.session.get(Producto, int(producto_id)):
        abort(400, description="producto no existe")

    # unicidad (par)
    exists = db.session.scalar(
        db.select(Catalogo.id).where(
            Catalogo.cliente_id == int(cliente_id),
            Catalogo.producto_id == int(producto_id)
        )
    )
    if exists:
        abort(409, description="ya existe catálogo para cliente+producto")

    c = Catalogo(cliente_id=int(cliente_id), producto_id=int(producto_id), estado="EN_PROCESO")
    db.session.add(c)
    db.session.flush()  # para tener c.id

    s = CatalogoSesion(catalogo_id=c.id, etiqueta=etiqueta, is_active=True)
    db.session.add(s)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad creando catálogo/sesión")

    # devolver catálogo con datos
    c = db.session.get(Catalogo, c.id)
    return jsonify(serialize_catalogo(c)), 201

@catalogo_bp.get("/<int:catalogo_id>")
@require_auth
def obtener_catalogo(catalogo_id: int):
    c = db.session.get(Catalogo, catalogo_id)
    if not c:
        abort(404)
    return jsonify(serialize_catalogo(c))

@catalogo_bp.get("/<int:catalogo_id>/final")
@require_auth
def obtener_final(catalogo_id: int):
    c = db.session.get(Catalogo, catalogo_id)
    if not c:
        abort(404)
    if not c.final_version_id or not c.final_version:
        abort(404, description="catálogo sin versión final")
    return jsonify(serialize_version(c.final_version))

@catalogo_bp.patch("/<int:catalogo_id>")
@require_auth
def editar_catalogo(catalogo_id: int):
    """
    Solo permite:
      - estado -> 'CANCELADA' si NO tiene final.
    'CERRADA' la marca el flujo de aprobación de Versiones.
    """
    c = db.session.get(Catalogo, catalogo_id)
    if not c:
        abort(404)
    data = request.get_json() or {}

    if "estado" in data:
        nuevo = (data.get("estado") or "").strip().upper()
        if nuevo not in ESTADOS_CATALOGO:
            abort(400, description="estado inválido")
        # no se permite editar si ya está cerrada
        if c.estado == "CERRADA":
            abort(409, description="catálogo cerrado: solo lectura")
        # no se puede marcar CERRADA manualmente
        if nuevo == "CERRADA":
            abort(409, description="estado CERRADA se asigna al aprobar una versión")
        # no se puede cancelar si ya tiene final
        if nuevo == "CANCELADA" and c.final_version_id is not None:
            abort(409, description="no se puede cancelar: ya tiene versión final")
        c.estado = nuevo

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad")
    return jsonify(serialize_catalogo(c))
