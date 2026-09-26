from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    environment: str
    refresh_token_expire_days: int
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_host: str | None = None
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: SecretStr | None = None
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    google_client_id: str | None = None
    # Optional until ingestion is enabled; ordinary HRMS routes need no API key.
    gemini_api_key: SecretStr | None = None
    embedding_model: Literal["gemini-embedding-2"] = "gemini-embedding-2"
    # Must match document_chunks.embedding. Changing size requires a migration.
    embedding_dimensions: int = Field(default=1536, ge=1536, le=1536)
    embedding_timeout_seconds: float = Field(default=30, gt=0, le=120)
    embedding_max_retries: int = Field(default=2, ge=0, le=5)
    rag_generation_model: Literal["gemini-3.5-flash-lite"] = "gemini-3.5-flash-lite"
    rag_top_k: int = Field(default=7, ge=1, le=10)
    # Cosine distance is 0 for identical directions; smaller is more relevant.
    rag_max_cosine_distance: float = Field(default=0.45, gt=0, lt=2)
    rag_generation_timeout_seconds: float = Field(default=30, gt=0, le=120)
    rag_generation_max_retries: int = Field(default=2, ge=0, le=5)

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Use asyncpg when Render supplies its standard PostgreSQL URL."""
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+asyncpg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def allowed_cors_origins(self) -> list[str]:
        origins = {
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        }
        if self.frontend_host:
            host = self.frontend_host.strip().rstrip("/")
            origins.add(host if "://" in host else f"https://{host}")
        return sorted(origins)


settings = Settings()
