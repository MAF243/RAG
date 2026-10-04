from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_", extra="ignore")
    google_api_key: SecretStr | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    model: str = "gemini-2.5-flash"
    embedding_model: str = "models/gemini-embedding-001"
    data_dir: Path = Path("data/v2")
    api_keys: dict[str, SecretStr] = Field(default_factory=dict)
    max_upload_mb: int = Field(default=20, ge=1, le=100)
    max_pages: int = Field(default=100, ge=1, le=500)
    max_chunks: int = Field(default=2000, ge=1, le=10000)
    max_extracted_chars: int = Field(default=1_000_000, ge=1000)
    max_documents_per_owner: int = Field(default=50, ge=1)
    chunk_size: int = Field(default=1000, ge=100, le=4000)
    chunk_overlap: int = Field(default=200, ge=0)
    top_k: int = Field(default=5, ge=1, le=20)
    max_cosine_distance: float = Field(default=0.65, ge=0, le=2)
    native_min_chars: int = Field(default=40, ge=0)
    ocr_dpi: int = Field(default=150, ge=72, le=300)
    max_render_pixels: int = Field(default=12_000_000, ge=1000)
    request_timeout: float = Field(default=60, gt=0, le=300)
    study_context_chunks: int = Field(default=16, ge=10, le=30)
    study_context_chars: int = Field(default=18000, ge=4000, le=40000)
    requests_per_minute: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def validate_settings(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP harus lebih kecil dari RAG_CHUNK_SIZE")
        keys = [key.get_secret_value() for key in self.api_keys.values()]
        if any(len(key) < 24 for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("API key harus unik dan memiliki minimal 24 karakter")
        return self


@lru_cache
def get_settings():
    return Settings()
