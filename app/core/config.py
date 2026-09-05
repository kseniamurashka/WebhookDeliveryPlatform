from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Webhook Delivery Platform"
    database_url: str
    redis_url: str
    api_key: str | None = None
    test_webhook_secret: str = "whsec_test_secret"
    delivery_timeout_seconds: float = 10.0
    max_response_body_length: int = 4096

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
