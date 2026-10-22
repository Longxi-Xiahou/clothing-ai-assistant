from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3307
    MYSQL_DATABASE: str = "clothing_ai"
    MYSQL_USER: str = "clothing_app"
    MYSQL_PASSWORD: str

    LLM_BASE_URL: str = "http://127.0.0.1:8102/v1"
    LLM_MODEL: str = "Qwen3-14B"
    LLM_TIMEOUT_SECONDS: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
