from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = "change-me"
    db_path: str = "./data/senryaku.db"
    timezone: str = "Pacific/Auckland"
    webhook_url: str = ""
    webhook_type: str = "ntfy"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    briefing_cron: str = "0 7 * * *"
    review_cron: str = "0 18 * * 0"
    base_url: str = "http://localhost:8000"

    model_config = {"env_prefix": "SENRYAKU_", "env_file": ".env"}


def get_settings() -> Settings:
    return Settings()
