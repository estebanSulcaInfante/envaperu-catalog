import os

class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/miapp")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Auth
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-too")
    JWT_ALG = "HS256"
    ACCESS_TTL_MIN = int(os.getenv("ACCESS_TTL_MIN", "15"))
    REFRESH_TTL_D = int(os.getenv("REFRESH_TTL_D", "7"))
    
class DevConfig(BaseConfig):
    DEBUG = True

class ProdConfig(BaseConfig):
    DEBUG = False

class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/miapp_test",
    )

def get_config(env_name: str | None):
    env = env_name or os.getenv("FLASK_ENV") or os.getenv("APP_ENV") or "development"
    if env.lower().startswith("prod"):
        return ProdConfig
    if env.lower().startswith("test"):
        return TestConfig
    return DevConfig
