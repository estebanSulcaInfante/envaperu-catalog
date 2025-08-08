# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Product(db.Model):
    __tablename__ = 'product'
    id         = db.Column(db.BigInteger, primary_key=True)
    family     = db.Column(db.Text, nullable=False)
    name       = db.Column(db.Text, nullable=False)
    peso_gr    = db.Column(db.Numeric)
    # campos opcionales si los quieres mapear:
    largo_cm   = db.Column(db.Numeric)
    ancho_cm   = db.Column(db.Numeric)
    alto_cm    = db.Column(db.Numeric)
    volumen_cbm= db.Column(db.Numeric)
    foto_url   = db.Column(db.Text)

    catalogs   = db.relationship('Catalog', back_populates='product')

class Catalog(db.Model):
    __tablename__ = 'catalog'
    id                   = db.Column(db.BigInteger, primary_key=True)
    product_id           = db.Column(db.BigInteger,
                                     db.ForeignKey('product.id'),
                                     nullable=False)
    um                   = db.Column(db.Text, nullable=False)
    doc_x_bulto_caja     = db.Column(db.Integer)
    doc_x_paq            = db.Column(db.Integer)
    cantidad_por_paquete = db.Column(db.Integer)
    cant_bultos          = db.Column(db.Integer)
    cant_paquetes        = db.Column(db.Integer)
    cant_unidades        = db.Column(db.Integer)
    cant_por_um          = db.Column(db.Integer)
    precio_exw           = db.Column(db.Numeric, nullable=False)
    precio_x_docena      = db.Column(db.Numeric)
    precio_unidad_exw    = db.Column(db.Numeric)
    subtotal_exw         = db.Column(db.Numeric)
    cbm_m3               = db.Column(db.Numeric)
    peso_neto            = db.Column(db.Numeric)
    peso_bruto           = db.Column(db.Numeric)
    descuento_pct        = db.Column(db.Numeric)
    precio_x_kilo        = db.Column(db.Numeric)

    product = db.relationship('Product', back_populates='catalogs')
