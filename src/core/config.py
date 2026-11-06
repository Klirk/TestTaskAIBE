from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    celery_broker_url: str

    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_rpm_limit: int
    llm_min_latency_seconds: float
    llm_max_latency_seconds: float

    worker_concurrency: int
    worker_poll_interval_seconds: float

    delivery_max_retries: int
    delivery_timeout_seconds: float

    mock_helpdesk_failure_rate: float


settings = Settings()
