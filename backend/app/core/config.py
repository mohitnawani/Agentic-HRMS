from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    environment: str
    refresh_token_expire_days: int
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    google_client_id: str | None = None
    # Optional until ingestion is enabled; ordinary HRMS routes need no API key.
    gemini_api_key: SecretStr | None = None
    embedding_model: Literal["gemini-embedding-2"] = "gemini-embedding-2"
    # Must match document_chunks.embedding. Changing size requires a migration.
    embedding_dimensions: Literal[1536] = 1536
    embedding_timeout_seconds: float = Field(default=30, gt=0, le=120)
    embedding_max_retries: int = Field(default=2, ge=0, le=5)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env"
    )


settings = Settings()
