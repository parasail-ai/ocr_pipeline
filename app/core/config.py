import json
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyUrl, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    app_name: str = "Parasail OCR Pipeline"
    environment: str = "dev"

    database_url: str = "postgresql+asyncpg://dbadmin:Warbiscuit511!@azure-databoard-db.postgres.database.azure.com/ocr?ssl=require"

    azure_storage_account_url: Optional[AnyUrl] = None
    azure_blob_container: str = "contracts"
    azure_storage_connection_string: Optional[str] = None

    parasail_api_key: Optional[str] = None
    parasail_base_url: AnyUrl = Field("https://api.parasail.io/v1")
    parasail_default_model: str = "parasail-matt-ocr-1-dots"

    docling_model_name: Optional[str] = None

    allowed_origins_raw: Optional[str | List[str]] = Field(
        default=None,
        validation_alias="ALLOWED_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="APP_", extra="ignore")

    @computed_field(return_type=List[str])
    @property
    def allowed_origins(self) -> List[str]:
        value = self.allowed_origins_raw

        if value is None:
            return ["*"]

        if isinstance(value, list):
            cleaned = [origin.strip() for origin in value if isinstance(origin, str) and origin.strip()]
            return cleaned or ["*"]

        # handle string values: attempt JSON parse, else treat as comma-separated list
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                cleaned = [str(origin).strip() for origin in parsed if str(origin).strip()]
                if cleaned:
                    return cleaned
        except json.JSONDecodeError:
            pass

        cleaned = [origin.strip() for origin in value.split(",") if origin.strip()]
        return cleaned or ["*"]


@lru_cache
def get_settings() -> Settings:
    """Cache settings so values are only loaded once."""
    return Settings()
