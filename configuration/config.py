from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from enum import Enum

class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"

class AppSettings(BaseSettings):
    ENVIRONMENT: Environment
    DEBUG: bool
    LOG_LEVEL: str
    CORS_ORIGINS: list[str] = ["*"]

    # Paramètres OpenTelemetry
    OTLP_ENDPOINT: str = "http://localhost:4317"  # Endpoint OTLP par défaut
    OTEL_SERVICE_NAME: str = "simplefastapiapp"
    OTEL_TRACES_EXPORTER: str = "otlp"
    
    model_config = {
        "env_file": os.getcwd() + '/.env',
        "case_sensitive": True
    }

class DBSettings(BaseSettings):
    DB_HOST: str
    DB_NAME: str
    DB_PASSWORD: str
    DB_USER: str
    DB_PORT: int

    model_config = {
        "env_file": os.getcwd() + '/.env_db',
        "case_sensitive": True
    }


class RedisSettings(BaseSettings):
    REDIS_HOST: str 
    REDIS_PORT: int 
    REDIS_PASSWORD: str 
    REDIS_DB: int = 0
    REDIS_TTL: int = 300  # Default TTL in seconds

    model_config = {
        "env_file": os.getcwd() + '/.env_redis',
        "case_sensitive": True
    }

@lru_cache
def get_app_settings():
    return AppSettings()

@lru_cache
def get_db_settings():
    return DBSettings()

@lru_cache
def get_redis_settings():
    return RedisSettings()