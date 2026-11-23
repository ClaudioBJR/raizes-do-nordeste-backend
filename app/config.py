from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "API Rede Raizes do Nordeste"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./raizes_nordeste.db"
    JWT_SECRET_KEY: str = "raizes-do-nordeste-chave-secreta-jwt-2026-minimo32chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_IN_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()