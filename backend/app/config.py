from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_rpm: int = 5
    gemini_daily_limit: int = 100

    # Summarization
    summary_min_chars: int = 1500
    summary_max_input_chars: int = 12000
    summary_max_attempts: int = 5

    # Fetching: entries published longer ago than this are ignored.
    fetch_max_age_hours: int = 48

    # Scheduler
    fetch_interval_minutes: int = 60
    scheduler_enabled: bool = True

    # App
    database_url: str = "sqlite:///./data/ai_news.db"
    admin_api_key: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
