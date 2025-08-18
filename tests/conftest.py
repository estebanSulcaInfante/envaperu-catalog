import os
import pytest
from app import create_app
from app.models import db, Cliente, Producto
from dotenv import load_dotenv
import sqlalchemy as sa

load_dotenv()

TEST_DB_URL = os.getenv(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://postgres:1234@localhost:5432/envaperu_catalog_test"
)
# Si prefieres no crear Postgres de test, usa SQLite:
# TEST_DB_URL = os.getenv("DATABASE_URL_TEST", "sqlite:///test.db")

def ensure_pg_database(db_url: str):
    from urllib.parse import urlparse, unquote
    import psycopg

    p = urlparse(db_url)
    dbname = p.path.lstrip("/")
    user = unquote(p.username or "postgres")
    password = unquote(p.password or "")
    host = p.hostname or "localhost"
    port = p.port or 5432

    admin_dsn = f"dbname=postgres user={user} password={password} host={host} port={port}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{dbname}";')


@pytest.fixture(scope="session")
def app():
    os.environ["APP_ENV"] = "test"
    app = create_app(
        env_name="test",
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": TEST_DB_URL,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        },
    )
    print(">> TEST DB URI =", TEST_DB_URL)

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    with app.app_context():
        db.drop_all()

@pytest.fixture(autouse=True)
def _reset_db_per_test(app):
    """Se ejecuta automáticamente alrededor de cada test."""
    yield
    with app.app_context():
        db.session.remove()
        tables = [t.name for t in db.metadata.sorted_tables]
        if tables:
            # "TRUNCATE … RESTART IDENTITY CASCADE" = borra todo y reinicia IDs
            stmt = "TRUNCATE TABLE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"
            db.session.execute(sa.text(stmt))
            db.session.commit()



@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def _reset_db_per_test(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()


def _auth_headers(client, email="tester@envaperu.local", password="Secret!123"):
    # intenta login; si no existe usuario, registra y vuelve a intentar
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code == 401:
        # crea primer usuario
        rr = client.post("/api/auth/register", json={"email": email, "password": password, "nombre": "Tester"})
        assert rr.status_code in (201, 403), rr.text
        r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    access = r.get_json()["access_token"]
    return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}

@pytest.fixture()
def auth_headers(client):
    return _auth_headers(client)

@pytest.fixture()
def seed_cliente_producto(app):
    # Inserta un cliente y producto base directamente en BD
    with app.app_context():
        c = Cliente(
            tipo_doc="RUC",
            num_doc="20123456789",
            nombre="Cliente S.A.",
            pais="PE",
            ciudad="Lima",
        )
        p = Producto(
            nombre="Detergente Pro X",
            um="DOC",
            doc_x_bulto_caja=5,
            doc_x_paq=10,
            precio_exw=12.34,
            familia="Limpieza",
            imagen_key=None,
        )
        db.session.add_all([c, p])
        db.session.commit()
        return {"cliente_id": c.id, "producto_id": p.id}
