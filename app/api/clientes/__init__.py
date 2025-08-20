# backend/blueprints/clientes.py
from flask import Blueprint, request, jsonify, abort, make_response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from ...models import db, Cliente
from ...decorators import require_auth

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

TIPOS_DOC = {"DNI","RUC","CE","PASAPORTE","OTRO"}

def serialize_cliente(c: Cliente) -> dict:
    return {
        "id": c.id,
        "tipo_doc": c.tipo_doc,
        "num_doc": c.num_doc,
        "nombre": c.nombre,
        "descripcion": c.descripcion,
        "pais": c.pais,
        "ciudad": c.ciudad,
        "zona": c.zona,
        "direccion": c.direccion,
        "clasificacion_riesgo": c.clasificacion_riesgo,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }

def _paginated(query):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        abort(400, description="page/per_page inválidos")
    per_page = max(1, min(per_page, 100))
    items = query.limit(per_page).offset((page-1)*per_page).all()
    return items, page, per_page

@clientes_bp.route("", methods=["GET", "OPTIONS"])
@clientes_bp.route("/", methods=["GET", "OPTIONS"])
@require_auth
def listar_clientes():
    if request.method == "OPTIONS":
        return make_response(("", 204))

    q = Cliente.query
    search = (request.args.get("search") or "").strip()
    pais = (request.args.get("pais") or "").strip()
    ciudad = (request.args.get("ciudad") or "").strip()

    if search:
        like = f"%{search.lower()}%"
        q = q.filter(
            func.lower(Cliente.nombre).like(like) |
            func.lower(Cliente.num_doc).like(like)
        )
    if pais:
        q = q.filter(Cliente.pais == pais)
    if ciudad:
        q = q.filter(Cliente.ciudad == ciudad)

    q = q.order_by(Cliente.created_at.desc(), Cliente.id.desc())
    items, page, per_page = _paginated(q)
    return jsonify({
        "data": [serialize_cliente(i) for i in items],
        "page": page, "per_page": per_page
    })

@clientes_bp.route("", methods=["POST", "OPTIONS"])
@clientes_bp.route("/", methods=["POST", "OPTIONS"])
@require_auth
def crear_cliente():
    if request.method == "OPTIONS":
        return make_response(("", 204))

    data = request.get_json() or {}
    tipo_doc = (data.get("tipo_doc") or "").strip().upper()
    num_doc  = (data.get("num_doc") or "").strip()
    nombre   = (data.get("nombre") or "").strip()
    if not tipo_doc or not num_doc or not nombre:
        abort(400, description="tipo_doc, num_doc y nombre son requeridos")
    if tipo_doc not in TIPOS_DOC:
        abort(400, description=f"tipo_doc inválido: {tipo_doc}")

    descripcion = data.get("descripcion") or data.get("description")
    c = Cliente(
        tipo_doc=tipo_doc, num_doc=num_doc, nombre=nombre,
        pais=data.get("pais"), ciudad=data.get("ciudad"),
        zona=data.get("zona"), direccion=data.get("direccion"),
        clasificacion_riesgo=(data.get("clasificacion_riesgo") or "MEDIO"),
        descripcion=descripcion
    )
    db.session.add(c)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description="cliente duplicado (tipo_doc + num_doc)")
    return jsonify(serialize_cliente(c)), 201

@clientes_bp.route("/<int:cliente_id>", methods=["GET", "OPTIONS"])
@require_auth
def obtener_cliente(cliente_id: int):
    if request.method == "OPTIONS":
        return make_response(("", 204))
    c = db.session.get(Cliente, cliente_id)
    if not c:
        abort(404)
    return jsonify(serialize_cliente(c))

@clientes_bp.route("/<int:cliente_id>", methods=["PATCH", "OPTIONS"])
@require_auth
def editar_cliente(cliente_id: int):
    if request.method == "OPTIONS":
        return make_response(("", 204))

    c = db.session.get(Cliente, cliente_id)
    if not c:
        abort(404)
    data = request.get_json() or {}

    if "tipo_doc" in data:
        val = (data["tipo_doc"] or "").strip().upper()
        if val and val not in TIPOS_DOC:
            abort(400, description="tipo_doc inválido")
        c.tipo_doc = val or c.tipo_doc

    if "num_doc" in data:
        nd = (data["num_doc"] or "").strip()
        c.num_doc = nd or c.num_doc

    for k in ["nombre","pais","ciudad","zona","direccion","clasificacion_riesgo","descripcion"]:
        if k in data:
            setattr(c, k, (data[k] or None))

    # Soporta 'description' si llega en vez de 'descripcion'
    if "description" in data and "descripcion" not in data:
        c.descripcion = data["description"] or None

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description="cliente duplicado (tipo_doc + num_doc)")
    return jsonify(serialize_cliente(c))

@clientes_bp.route("/<int:cliente_id>", methods=["DELETE", "OPTIONS"])
@require_auth
def eliminar_cliente(cliente_id: int):
    if request.method == "OPTIONS":
        return make_response(("", 204))
    c = db.session.get(Cliente, cliente_id)
    if not c:
        abort(404)
    db.session.delete(c)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description="no se puede borrar: cliente referenciado")
    return jsonify({"ok": True})
