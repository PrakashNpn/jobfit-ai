from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None  # read from .env; falls back to the SDK's own lookup
    claude_model: str = "claude-sonnet-5-5"
    database_url: str = "postgresql+psycopg://jobfit:jobfit@localhost:6024/jobfit"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_size: int = 384  # must match embedding_model
    table_name: str = "document_chunks"
    chunk_size: int = 800
    chunk_overlap: int = 120


settings = Settings()
