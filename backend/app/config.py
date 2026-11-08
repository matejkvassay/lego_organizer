from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "sqlite:///./data/lego.db"

    brickset_api_key: str = ""
    brickset_base_url: str = "https://brickset.com/api/v3.asmx"

    openai_api_key: str = ""
    agent_model: str = "gpt-6-luna"
    transcribe_model: str = "gpt-4o-transcribe"
    agent_max_steps: int = 3
    agent_reasoning_effort: str = "none"  # empty string = provider default

    # Auth
    allowed_email: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = "change-me"
    base_url: str = "http://localhost:8000"

    frontend_dist: str = "../frontend/dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
