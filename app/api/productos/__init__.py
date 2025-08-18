from flask import Blueprint, request, jsonify, abort
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from ...models import db, Producto
from ...decorators import require_auth

productos_bp = Blueprint("productos", __name__, url_prefix="/productos")

UM_VALIDAS = {"DOC","UNID","CIENTO"}

def _num(n):
    return float(n) if n is not None else None

def serialize_producto(p: Producto) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "um": p.um,
        "doc_x_bulto_caja": _num(p.doc_x_bulto_caja),
        "doc_x_paq": _num(p.doc_x_paq),
        "precio_exw": _num(p.precio_exw),
        "familia": p.familia,
        "imagen_key": p.imagen_key,
        "created_at": p.created_at.isoformat() if p.created_at else None,
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

@productos_bp.get("")
@require_auth
def listar_productos():
    q = Producto.query
    search = (request.args.get("search") or "").strip()
    familia = (request.args.get("familia") or "").strip()

    if search:
        like = f"%{search.lower()}%"
        q = q.filter(func.lower(Producto.nombre).like(like))
    if familia:
        q = q.filter(Producto.familia == familia)

    q = q.order_by(Producto.created_at.desc(), Producto.id.desc())
    items, page, per_page = _paginated(q)
    return jsonify({
        "data": [serialize_producto(i) for i in items],
        "page": page, "per_page": per_page
    })

@productos_bp.post("")
@require_auth
def crear_producto():
    data = request.get_json() or {}
    required = ["nombre","um","doc_x_bulto_caja","doc_x_paq","precio_exw","familia"]
    if any(k not in data for k in required):
        abort(400, description=f"campos requeridos: {', '.join(required)}")

    um = (data.get("um") or "").strip().upper()
    if um not in UM_VALIDAS:
        abort(400, description="um inválida (DOC|UNID|CIENTO)")

    try:
        p = Producto(
            nombre=(data.get("nombre") or "").strip(),
            um=um,
            doc_x_bulto_caja=data.get("doc_x_bulto_caja"),
            doc_x_paq=data.get("doc_x_paq"),
            precio_exw=data.get("precio_exw"),
            familia=(data.get("familia") or "").strip(),
        )
        db.session.add(p)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad (valores inválidos)")
    return jsonify(serialize_producto(p)), 201

@productos_bp.get("/<int:producto_id>")
@require_auth
def obtener_producto(producto_id: int):
    p = db.session.get(Producto, producto_id)
    if not p:
        abort(404)
    return jsonify(serialize_producto(p))

@productos_bp.patch("/<int:producto_id>")
@require_auth
def editar_producto(producto_id: int):
    p = db.session.get(Producto, producto_id)
    if not p:
        abort(404)
    data = request.get_json() or {}

    if "um" in data:
        um = (data.get("um") or "").strip().upper()
        if um and um not in UM_VALIDAS:
            abort(400, description="um inválida (DOC|UNID|CIENTO)")
        p.um = um or p.um

    for k in ["nombre","familia","imagen_key"]:
        if k in data:
            setattr(p, k, (data[k] or None))

    for k in ["doc_x_bulto_caja","doc_x_paq","precio_exw"]:
        if k in data:
            setattr(p, k, data[k])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(400, description="error de integridad (valores inválidos)")
    return jsonify(serialize_producto(p))

@productos_bp.patch("/<int:producto_id>/imagen")
@require_auth
def actualizar_imagen(producto_id: int):
    import re, secrets
    from datetime import datetime

    def slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

    p = db.session.get(Producto, producto_id)
    if not p:
        abort(404)

    data = request.get_json() or {}
    key = data.get("imagen_key")
    filename = (data.get("filename") or "").lower()

    if not key:
        # Deriva extensión de filename; default .jpg
        m = re.search(r"\.(png|jpg|jpeg|webp|gif)$", filename)
        ext = "." + m.group(1) if m else ".jpg"

        slug = slugify(p.nombre or f"producto-{p.id}")
        rand = secrets.token_hex(4)  # 8 chars
        # carpeta por ID con padding para mantener orden
        key = f"productos/{p.id:06d}/{slug}-{rand}{ext}"

    p.imagen_key = key
    db.session.commit()
    return jsonify({"ok": True, "imagen_key": p.imagen_key})

@productos_bp.post("/<int:producto_id>/imagen/upload")
@require_auth
def subir_imagen(producto_id: int):
    import re, secrets, requests
    from flask import current_app

    def slugify(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

    p = db.session.get(Producto, producto_id)
    if not p:
        abort(404)

    f = request.files.get("file")  # multipart/form-data, key: file
    if not f:
        abort(400, description="file requerido (multipart/form-data)")

    # Debe existir imagen_key previamente generado vía PATCH /imagen
    if not p.imagen_key:
        abort(400, description="imagen_key no establecido: utiliza PATCH /imagen primero")

    # Validaciones de tipo y tamaño
    ALLOWED_MIME = {"image/png","image/jpeg","image/webp","image/gif"}
    if f.mimetype not in ALLOWED_MIME:
        abort(400, description="tipo de archivo no permitido")
    max_bytes = 5 * 1024 * 1024  # 5 MB
    if request.content_length and request.content_length > max_bytes:
        abort(400, description="archivo excede 5 MB")

    bucket = current_app.config["SUPABASE_BUCKET"]
    supa_url = current_app.config["SUPABASE_URL"].rstrip("/")
    service_key = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]

    if not supa_url or not service_key:
        abort(500, description="SUPABASE_URL o SERVICE_ROLE_KEY no configurados")

    # Subida via REST (x-upsert permite reemplazar)
    url = f"{supa_url}/storage/v1/object/{bucket}/{p.imagen_key}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "x-upsert": "true",
    }
    files = {"file": (f.filename, f.stream, f.mimetype or "application/octet-stream")}
    r = requests.post(url, headers=headers, files=files)
    if r.status_code >= 400:
        abort(r.status_code, description=f"supabase error: {r.text}")

    return jsonify({"ok": True, "imagen_key": p.imagen_key}), 200

@productos_bp.get("/<int:producto_id>/imagen/url")
@require_auth
def url_imagen(producto_id: int):
    import requests
    from flask import current_app

    p = db.session.get(Producto, producto_id)
    if not p or not p.imagen_key:
        abort(404)

    bucket = current_app.config["SUPABASE_BUCKET"]
    supa_url = current_app.config["SUPABASE_URL"].rstrip("/")
    service_key = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]

    # Tiempo en segundos (máx 24h = 86400)
    try:
        expires_in = int(request.args.get("expires_in", 3600))
    except ValueError:
        abort(400, description="expires_in inválido")
    if expires_in < 60 or expires_in > 86400:
        abort(400, description="expires_in debe estar entre 60 y 86400 segundos")

    url = f"{supa_url}/storage/v1/object/sign/{bucket}/{p.imagen_key}"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
        json={"expiresIn": expires_in},
    )
    if r.status_code >= 400:
        abort(r.status_code, description=f"supabase error: {r.text}")

    data = r.json()
    # La API devuelve un path firmado relativo; compón la URL completa:
    signed_url = f"{supa_url}/storage/v1/{data.get('signedURL')}"
    return jsonify({"url": signed_url, "expires_in": expires_in})


@productos_bp.delete("/<int:producto_id>")
@require_auth
def eliminar_producto(producto_id: int):
    p = db.session.get(Producto, producto_id)
    if not p:
        abort(404)
    db.session.delete(p)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        # probablemente referenciado por catalogo (RESTRICT)
        abort(409, description="no se puede borrar: producto referenciado")
    return jsonify({"ok": True})
