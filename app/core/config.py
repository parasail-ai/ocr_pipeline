from functools import lru_cache
from typing import List, Optional

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    app_name: str = "Parasail OCR Pipeline"
    environment: str = "dev"

    database_url: str = "postgresql://dbadmin:Warbiscuit511!@azure-databoard-db.postgres.database.azure.com/ocr?sslmode=require"

    azure_storage_account_url: Optional[AnyUrl] = None
    azure_blob_container: str = "contracts"
    azure_storage_connection_string: Optional[str] = None

    parasail_api_key: Optional[str] = None
    parasail_base_url: AnyUrl = Field("https://api.parasail.io/v1")
    parasail_default_model: str = "parasail-matt-ocr-1-dots"

    docling_model_name: Optional[str] = None

    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="APP_", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Cache settings so values are only loaded once."""
    return Settings()
