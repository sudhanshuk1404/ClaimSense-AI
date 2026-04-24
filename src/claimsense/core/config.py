from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="ClaimSense AI", alias="CLAIMSENSE_APP_NAME")
    env: str = Field(default="local", alias="CLAIMSENSE_ENV")
    host: str = Field(default="0.0.0.0", alias="CLAIMSENSE_HOST")
    port: int = Field(default=8000, alias="CLAIMSENSE_PORT")
    workers: int = Field(default=2, alias="CLAIMSENSE_WORKERS")
    log_level: str = Field(default="INFO", alias="CLAIMSENSE_LOG_LEVEL")
    root_path: str = Field(default="", alias="CLAIMSENSE_ROOT_PATH")
    knowledge_dir: Path = Field(default=Path("knowledge"), alias="CLAIMSENSE_KNOWLEDGE_DIR")
    prompts_dir: Path = Field(default=Path("prompts"), alias="CLAIMSENSE_PROMPTS_DIR")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

