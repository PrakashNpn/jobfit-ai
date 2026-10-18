from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None  # read from .env; falls back to the SDK's own lookup
    claude_model: str = "claude-haiku-5-5"
    database_url: str = "postgresql+psycopg://jobfit:jobfit@localhost:6024/jobfit"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_size: int = 384  # must match embedding_model
    table_name: str = "document_chunks"
    chunk_size: int = 800
    chunk_overlap: int = 120

    # Web app
    allowed_origins: str = "http://localhost:3000"  # comma-separated list for CORS
    max_job_chars: int = 15_000
    max_resume_chars: int = 20_000
    max_upload_bytes: int = 5 * 1024 * 1024
    # Set false on a public demo so visitors can't write to the shared database
    enable_rag_endpoints: bool = True

    # Usage limits for a public demo (0 = unlimited, the default for local use)
    daily_limit_per_visitor: int = 0
    daily_limit_total: int = 0
    daily_fetch_limit_per_visitor: int = 0  # job links read per visitor per day


settings = Settings()
