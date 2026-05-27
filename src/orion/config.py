from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORION_", env_file=".env")

    # App
    app_name: str = "Orion Agent Platform"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Temporal
    temporal_host: str = "localhost"
    temporal_port: int = 7233
    temporal_namespace: str = "default"
    temporal_task_queue: str = "orion-task-queue"

    # PostgreSQL
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orion"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_channel: str = "orion:streams"

    # Security
    api_key: str | None = None
    jwt_secret: str | None = None

    # Observability
    otel_endpoint: str | None = None
    otel_service_name: str = "orion-platform"

    # Retry defaults
    default_max_retries: int = 3
    default_retry_backoff: float = 1.0
    default_retry_max_wait: int = 30


settings = Settings()
