# app.py
import os
from flask import Flask, request, jsonify, abort
from models import db, Product, Catalog
from flask_cors import CORS
from sqlalchemy.orm import joinedload

app = Flask(__name__)
CORS(app)

# 1) Configurar la URL de conexión ()
DB_URL = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 2) Inicializar SQLAlchemy
db.init_app(app)

# 3) Crear tablas (solo la primera vez)
with app.app_context():
    db.create_all()

# --------- RUTAS PRODUCT ---------

# Listar todos los productos
@app.route('/products', methods=['GET'])
def list_products():
    # lee ?page=2&per_page=20, por defecto page=1, per_page=10
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 10, type=int)

    pagination = Product.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    items = [{
        'id':       p.id,
        'family':   p.family,
        'name':     p.name,
        'peso_gr':  float(p.peso_gr or 0)
    } for p in pagination.items]

    return jsonify({
        'items':    items,
        'total':    pagination.total,    # total de registros
        'pages':    pagination.pages,    # total de páginas
        'page':     pagination.page,     # página actual
        'per_page': pagination.per_page, # ítems por página
    })
# Crear un producto
@app.route('/products', methods=['POST'])
def create_product():
    data = request.get_json()
    p = Product(
        family  = data['family'],
        name    = data['name'],
        peso_gr = data.get('peso_gr')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'id': p.id}), 201

# Obtener un producto por id
@app.route('/products/<int:prod_id>', methods=['GET'])
def get_product(prod_id):
    p = Product.query.get_or_404(prod_id)
    return jsonify({
        'id': p.id, 'family': p.family, 'name': p.name, 'peso_gr': str(p.peso_gr)
    })

# Actualizar un producto
@app.route('/products/<int:prod_id>', methods=['PUT'])
def update_product(prod_id):
    p = Product.query.get_or_404(prod_id)
    data = request.get_json()
    p.family  = data.get('family', p.family)
    p.name    = data.get('name', p.name)
    p.peso_gr = data.get('peso_gr', p.peso_gr)
    db.session.commit()
    return jsonify({'message': 'Producto actualizado'})

# Borrar un producto
@app.route('/products/<int:prod_id>', methods=['DELETE'])
def delete_product(prod_id):
    p = Product.query.get_or_404(prod_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Producto eliminado'})

# --------- RUTAS CATALOG ---------

# Listar todos los catálogos
@app.route('/catalogs', methods=['GET'])
def list_catalogs():
    # Parámetros de paginación
    page     = request.args.get('page',     1,  type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Carga en una sola consulta también la relación Product
    pagination = Catalog.query \
        .options(joinedload(Catalog.product)) \
        .paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for c in pagination.items:
        prod = c.product
        items.append({
            # campos de catalog...
            'id':                   c.id,
            'um':                   c.um,
            'doc_x_bulto_caja':     c.doc_x_bulto_caja,
            'doc_x_paq':            c.doc_x_paq,
            'cantidad_por_paquete': c.cantidad_por_paquete,
            'cant_bultos':          c.cant_bultos,
            'cant_paquetes':        c.cant_paquetes,
            'cant_unidades':        c.cant_unidades,
            'cant_por_um':          c.cant_por_um,
            'precio_exw':           float(c.precio_exw),
            'precio_x_docena':      float(c.precio_x_docena or 0),
            'precio_unidad_exw':    float(c.precio_unidad_exw or 0),
            'subtotal_exw':         float(c.subtotal_exw or 0),
            'cbm_m3':               float(c.cbm_m3 or 0),
            'peso_neto':            float(c.peso_neto or 0),
            'peso_bruto':           float(c.peso_bruto or 0),
            'descuento_pct':        float(c.descuento_pct or 0),
            'precio_x_kilo':        float(c.precio_x_kilo or 0),

            # campos extendidos de product
            'product': {
                'id':         prod.id,
                'family':     prod.family,
                'name':       prod.name,
                'peso_gr':    float(prod.peso_gr or 0),
                'largo_cm':   float(prod.largo_cm)   if prod.largo_cm  is not None else None,
                'ancho_cm':   float(prod.ancho_cm)   if prod.ancho_cm  is not None else None,
                'alto_cm':    float(prod.alto_cm)    if prod.alto_cm   is not None else None,
                'volumen_cbm':float(prod.volumen_cbm)if prod.volumen_cbm is not None else None,
                'foto_url':   prod.foto_url          if prod.foto_url  is not None else None,
            }
        })

    return jsonify({
        'items':    items,
        'total':    pagination.total,
        'pages':    pagination.pages,
        'page':     pagination.page,
        'per_page': pagination.per_page
    })
    
# Crear un catálogo
@app.route('/catalogs', methods=['POST'])
def create_catalog():
    data = request.get_json()
    if not Product.query.get(data['product_id']):
        abort(400, 'product_id inválido')
    c = Catalog(**data)
    db.session.add(c)
    db.session.commit()
    return jsonify({'id': c.id}), 201

# Obtener un catálogo por id
@app.route('/catalogs/<int:cat_id>', methods=['GET'])
def get_catalog(cat_id):
    c = Catalog.query.get_or_404(cat_id)
    return jsonify({
        'id': c.id,
        'product_id': c.product_id,
        'um': c.um,
        'precio_exw': str(c.precio_exw),
        # añade más campos según necesites...
    })

# Actualizar un catálogo
@app.route('/catalogs/<int:cat_id>', methods=['PUT'])
def update_catalog(cat_id):
    c = Catalog.query.get_or_404(cat_id)
    data = request.get_json()
    for key, val in data.items():
        if hasattr(c, key):
            setattr(c, key, val)
    db.session.commit()
    return jsonify({'message': 'Catálogo actualizado'})

# Borrar un catálogo
@app.route('/catalogs/<int:cat_id>', methods=['DELETE'])
def delete_catalog(cat_id):
    c = Catalog.query.get_or_404(cat_id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Catálogo eliminado'})

# -----------------------------

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
