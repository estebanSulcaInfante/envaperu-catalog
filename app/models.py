# models.py
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy import CheckConstraint, UniqueConstraint, Index, case
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy import ForeignKeyConstraint

db = SQLAlchemy()

# -------------------------
# CLIENTE
# -------------------------
class Cliente(db.Model):
    __tablename__ = "cliente"

    id = db.Column(db.BigInteger, primary_key=True)

    tipo_doc = db.Column(db.String(20), nullable=False)  # DNI | RUC | CE | PASAPORTE | OTRO
    num_doc  = db.Column(db.String(80), nullable=False)  # número de doc identidad
    nombre   = db.Column(db.Text, nullable=False)

    pais      = db.Column(db.Text)
    ciudad    = db.Column(db.Text)
    zona      = db.Column(db.Text)
    direccion = db.Column(db.Text)

    clasificacion_riesgo = db.Column(db.String(10), nullable=False, default="MEDIO")  # BAJO|MEDIO|ALTO

    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        CheckConstraint("tipo_doc in ('DNI','RUC','CE','PASAPORTE','OTRO')", name="chk_cliente_tipo_doc"),
        CheckConstraint("clasificacion_riesgo in ('BAJO','MEDIO','ALTO')",   name="chk_cliente_riesgo"),
        UniqueConstraint("tipo_doc", "num_doc", name="uq_cliente_doc"),
        sa.Index("idx_cliente_nombre_ci", sa.func.lower(nombre)),
        sa.Index("idx_cliente_pais_ciudad", pais, ciudad),
    )

    catalogos = relationship("Catalogo", back_populates="cliente")


# -------------------------
# PRODUCTO (maestro)
# -------------------------
class Producto(db.Model):
    __tablename__ = "producto"
    id = db.Column(db.BigInteger, primary_key=True)

    nombre           = db.Column(db.Text, nullable=False)
    um               = db.Column(db.String(10), nullable=False)  # 'DOC'|'UNID'|'CIENTO'
    doc_x_bulto_caja = db.Column(NUMERIC(10, 2), nullable=False)     # antes: Numeric genérico
    doc_x_paq        = db.Column(NUMERIC(10, 2), nullable=False)     # antes: Numeric genérico
    precio_exw       = db.Column(NUMERIC(12, 4), nullable=False)
    familia          = db.Column(db.Text, nullable=False)
    imagen_key       = db.Column(db.Text)
    created_at       = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        CheckConstraint("um in ('DOC','UNID','CIENTO')", name="chk_producto_um"),
        CheckConstraint("precio_exw >= 0",               name="chk_producto_precio"),
        sa.Index("idx_producto_nombre", nombre),
    )
    
    catalogos = relationship("Catalogo", back_populates="producto")


# -------------------------
# CATALOGO (una negociación por cliente–producto)
# -------------------------
class Catalogo(db.Model):
    __tablename__ = "catalogo"
    id = db.Column(db.BigInteger, primary_key=True)

    cliente_id  = db.Column(db.BigInteger, db.ForeignKey("cliente.id", ondelete="RESTRICT"), nullable=False)
    producto_id = db.Column(db.BigInteger, db.ForeignKey("producto.id", ondelete="RESTRICT"), nullable=False)

    final_version_id = db.Column(db.BigInteger)  # quitamos FK simple

    estado     = db.Column(db.String(20), nullable=False, default="EN_PROCESO")
    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        UniqueConstraint("cliente_id", "producto_id", name="uq_catalogo_cliente_producto"),
        CheckConstraint("estado in ('EN_PROCESO','CERRADA','CANCELADA')", name="chk_catalogo_estado"),
        sa.Index("idx_catalogo_cliente", cliente_id),
        sa.Index("idx_catalogo_producto", producto_id),

        # FK compuesta: (final_version_id, id) -> (version.id, version.catalogo_id)
        ForeignKeyConstraint(
            ["final_version_id", "id"],
            ["catalogo_sesion_version.id", "catalogo_sesion_version.catalogo_id"],
            name="fk_catalogo_final_belongs",
            ondelete="SET NULL",
        ),
    )

    cliente  = relationship("Cliente",  back_populates="catalogos")
    producto = relationship("Producto", back_populates="catalogos")
    sesiones = relationship("CatalogoSesion", back_populates="catalogo", cascade="all, delete-orphan")
    final_version = relationship("CatalogoSesionVersion", foreign_keys=[final_version_id], uselist=False)


# -------------------------
# SESIONES (hilos paralelos en un catálogo)
# -------------------------
class CatalogoSesion(db.Model):
    __tablename__ = "catalogo_sesion"

    id = db.Column(db.BigInteger, primary_key=True)
    catalogo_id = db.Column(db.BigInteger, db.ForeignKey("catalogo.id", ondelete="CASCADE"), nullable=False)

    etiqueta  = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.Index("idx_sesion_catalogo", catalogo_id),
        # Para poder referenciar (id, catalogo_id) desde Version:
        UniqueConstraint("id", "catalogo_id", name="uq_sesion_id_catalogo"),
    )

    catalogo  = relationship("Catalogo", back_populates="sesiones")
    versiones = relationship(
        "CatalogoSesionVersion",
        back_populates="sesion",
        cascade="all, delete-orphan",
        order_by="CatalogoSesionVersion.version_num",
        foreign_keys="CatalogoSesionVersion.sesion_id",
    )


# -------------------------
# VERSIONES (histórico con snapshot)
# -------------------------
class CatalogoSesionVersion(db.Model):
    __tablename__ = "catalogo_sesion_version"

    id = db.Column(db.BigInteger, primary_key=True)

    sesion_id   = db.Column(db.BigInteger, db.ForeignKey("catalogo_sesion.id", ondelete="CASCADE"), nullable=False)
    catalogo_id = db.Column(db.BigInteger, db.ForeignKey("catalogo.id", ondelete="CASCADE"),         nullable=False)
    producto_id = db.Column(db.BigInteger, db.ForeignKey("producto.id", ondelete="RESTRICT"),         nullable=False)

    # Relación inversa hacia CatalogoSesion
    sesion = relationship(
        "CatalogoSesion",
        back_populates="versiones",
        foreign_keys=[sesion_id],
    )

    version_num = db.Column(db.Integer, nullable=False)

    estado     = db.Column(db.String(20), nullable=False, default="BORRADOR")
    is_current = db.Column(db.Boolean,     nullable=False, default=True)
    is_final   = db.Column(db.Boolean,     nullable=False, default=False)

    # SNAPSHOT (con precisión y defaults donde convenga)
    um               = db.Column(db.String(10), nullable=False)
    doc_x_bulto_caja = db.Column(NUMERIC(10, 2))
    doc_x_paq        = db.Column(NUMERIC(10, 2), nullable=False)
    precio_exw       = db.Column(NUMERIC(12, 4), nullable=False)
    porc_desc        = db.Column(NUMERIC(5, 4))                  # 0.15 = 15%
    cant_bultos      = db.Column(NUMERIC(10, 2), nullable=False, server_default="0")
    peso_gr          = db.Column(NUMERIC(10, 2))
    largo_cm         = db.Column(NUMERIC(10, 2))
    ancho_cm         = db.Column(NUMERIC(10, 2))
    alto_cm          = db.Column(NUMERIC(10, 2))
    familia          = db.Column(db.Text)
    foto_key         = db.Column(db.Text)
    observaciones    = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        UniqueConstraint("sesion_id", "version_num", name="uq_version_por_sesion"),
        UniqueConstraint("id", "catalogo_id", name="uq_version_id_catalogo"),
        CheckConstraint("um in ('DOC','UNID','CIENTO')", name="chk_version_um"),
        CheckConstraint("precio_exw >= 0",               name="chk_version_precio"),
        CheckConstraint("estado in ('BORRADOR','ENVIADA','CONTRAOFERTA','APROBADA','RECHAZADA','EXPIRADA')",
                        name="chk_version_estado"),
        CheckConstraint("version_num >= 1",              name="chk_version_num_pos"),
        CheckConstraint("doc_x_paq is null or doc_x_paq >= 0",        name="chk_doc_x_paq_nonneg"),
        CheckConstraint("cant_bultos >= 0",                             name="chk_cant_bultos_nonneg"),
        CheckConstraint("peso_gr is null or peso_gr >= 0",             name="chk_peso_gr_nonneg"),
        CheckConstraint("largo_cm is null or largo_cm >= 0",           name="chk_largo_nonneg"),
        CheckConstraint("ancho_cm is null or ancho_cm >= 0",           name="chk_ancho_nonneg"),
        CheckConstraint("alto_cm  is null or alto_cm  >= 0",           name="chk_alto_nonneg"),
        CheckConstraint("(is_final = FALSE) OR (estado = 'APROBADA')", name="chk_final_aprobada"),

        # ÍNDICES parciales (PostgreSQL)
        Index("uq_sesion_current", sesion_id, unique=True, postgresql_where=sa.text("is_current")),
        Index("uq_sesion_final",   sesion_id, unique=True, postgresql_where=sa.text("is_final")),
        Index("uq_catalogo_final_total", catalogo_id, unique=True, postgresql_where=sa.text("is_final")),

        # FK compuesta: obliga a que catalogo_id coincida con el de la sesión
        ForeignKeyConstraint(
            ["sesion_id", "catalogo_id"],
            ["catalogo_sesion.id", "catalogo_sesion.catalogo_id"],
            name="fk_version_sesion_catalogo",
            ondelete="CASCADE",
        ),
    )

    # -------------------------
    # COLUMNAS CALCULADAS (se ejecutan en la BD)
    # -------------------------

    # PRECIO x DOCENA = ROUND(precio_exw * (1 - porc_desc), 2)
    precio_x_docena = db.column_property(
        sa.func.round(
            (sa.cast(precio_exw, sa.Numeric) * (1 - sa.func.coalesce(porc_desc, 0))),
            2
        )
    )

    # Cantidad por Paquete = CASE(um)
    cantidad_por_paquete = db.column_property(
        case(
            (um == 'DOC',    doc_x_paq * 12),
            (um == 'UNID',   doc_x_paq),
            (um == 'CIENTO', doc_x_paq * 100),
            else_=None
        )
    )

    # Precio Unidad (EXW) = precio_x_docena / divisor(um)
    precio_unidad_exw = db.column_property(
        precio_x_docena / case(
            (um == 'DOC', 12),
            (um == 'UNID', 1),
            (um == 'CIENTO', 100),
            else_=None
        )
    )

    # Volumen Paquete (m^3) (cm -> m)
    volumen_paquete_cbm = db.column_property(
        (sa.func.coalesce(largo_cm, 0) / 100.0) *
        (sa.func.coalesce(ancho_cm, 0) / 100.0) *
        (sa.func.coalesce(alto_cm,  0) / 100.0)
    )

    # Cantidad Unidades por bultos
    cantidad_unidades = db.column_property(
        case(
            (um == 'DOC',    doc_x_paq * 12  * cant_bultos),
            (um == 'UNID',   doc_x_paq       * cant_bultos),
            (um == 'CIENTO', doc_x_paq * 100 * cant_bultos),
            else_=None
        )
    )

    # Subtotal EXW = bultos * doc_x_paq * precio_unidad_exw
    subtotal_exw = db.column_property(
        sa.func.coalesce(cant_bultos, 0) * sa.func.coalesce(doc_x_paq, 0) * precio_unidad_exw
    )

    # CBM total = volumen_paquete_cbm * bultos
    cbm_total = db.column_property(
        volumen_paquete_cbm * sa.func.coalesce(cant_bultos, 0)
    )

    # Peso neto (kg) = peso_gr * cantidad_unidades / 1000
    peso_neto_kg = db.column_property(
        (sa.func.coalesce(peso_gr, 0) *
         case(
             (um == 'DOC',    sa.func.coalesce(doc_x_paq, 0) * 12  * sa.func.coalesce(cant_bultos, 0)),
             (um == 'UNID',   sa.func.coalesce(doc_x_paq, 0)       * sa.func.coalesce(cant_bultos, 0)),
             (um == 'CIENTO', sa.func.coalesce(doc_x_paq, 0) * 100 * sa.func.coalesce(cant_bultos, 0)),
             else_=0
         )) / 1000.0
    )

    # Peso bruto (kg) = peso_neto + 1.5 kg * bulto (ajusta la tara si difiere)
    peso_bruto_kg = db.column_property(
        ((sa.func.coalesce(peso_gr, 0) *
          case(
              (um == 'DOC',    sa.func.coalesce(doc_x_paq, 0) * 12  * sa.func.coalesce(cant_bultos, 0)),
              (um == 'UNID',   sa.func.coalesce(doc_x_paq, 0)       * sa.func.coalesce(cant_bultos, 0)),
              (um == 'CIENTO', sa.func.coalesce(doc_x_paq, 0) * 100 * sa.func.coalesce(cant_bultos, 0)),
              else_=0
          )) / 1000.0) + 1.5 * sa.func.coalesce(cant_bultos, 0)
    )

# models_auth.py
class Usuario(db.Model):
    __tablename__ = "usuario"
    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String, nullable=False)  # quitamos unique del Column...
    pass_hash = db.Column(db.Text, nullable=False)
    nombre = db.Column(db.Text, nullable=False)
    cargo = db.Column(db.Text)
    estado = db.Column(db.String, nullable=False, default="ACTIVO")
    #mfa_totp_secret = db.Column(db.Text)
    last_login_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())
    roles = db.relationship("Rol", secondary="usuario_rol", back_populates="usuarios")

    __table_args__ = (
        CheckConstraint("estado in ('ACTIVO','SUSPENDIDO','BAJA')", name="chk_usuario_estado"),
        # Único case-insensitive:
        sa.Index("uq_usuario_email_lower", sa.func.lower(email), unique=True),
    )

class Rol(db.Model):
    __tablename__ = "rol"
    id = db.Column(db.BigInteger, primary_key=True)
    nombre = db.Column(db.String, unique=True, nullable=False)
    permisos = db.relationship("Permiso", secondary="rol_permiso", back_populates="roles")
    usuarios = db.relationship("Usuario", secondary="usuario_rol", back_populates="roles")

class Permiso(db.Model):
    __tablename__ = "permiso"
    id = db.Column(db.BigInteger, primary_key=True)
    clave = db.Column(db.String, unique=True, nullable=False)
    descripcion = db.Column(db.Text)
    roles = db.relationship("Rol", secondary="rol_permiso", back_populates="permisos")

class UsuarioRol(db.Model):
    __tablename__ = "usuario_rol"
    usuario_id = db.Column(db.BigInteger, db.ForeignKey("usuario.id"), primary_key=True)
    rol_id = db.Column(db.BigInteger, db.ForeignKey("rol.id"), primary_key=True)

class RolPermiso(db.Model):
    __tablename__ = "rol_permiso"
    rol_id = db.Column(db.BigInteger, db.ForeignKey("rol.id"), primary_key=True)
    permiso_id = db.Column(db.BigInteger, db.ForeignKey("permiso.id"), primary_key=True)

class RefreshToken(db.Model):
    __tablename__ = "refresh_token"
    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(db.BigInteger, db.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.Text)
    ip = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=sa.func.now())
    revoked_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        sa.Index("idx_rt_user_open", "usuario_id", postgresql_where=sa.text("revoked_at IS NULL")),
        sa.Index("idx_rt_created", "created_at"),
    )
