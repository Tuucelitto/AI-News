from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_rpm: int = 4
    gemini_daily_limit: int = 18
    # Used while the main model is failing or out of quota. Empty disables the fallback.
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_rpm: int = 12
    gemini_fallback_daily_limit: int = 45

    # Summarization
    summary_min_chars: int = 500
    summary_max_input_chars: int = 12000
    summary_max_attempts: int = 5
    summary_batch_size: int = 5  # articles per Gemini request

    # Fetching: entries published longer ago than this are ignored.
    fetch_max_age_hours: int = 48

    # Scheduler
    fetch_interval_minutes: int = 60
    summary_interval_seconds: int = 15  # how often the queue worker checks for work
    scheduler_enabled: bool = True

    # App
    database_url: str = "sqlite:///./data/ai_news.db"
    admin_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
