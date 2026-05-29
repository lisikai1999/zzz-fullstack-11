from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./scheduler.db"
    scheduler_tick_interval: int = 60
    simulated_execution_seconds: float = 2.0
    serial_queue_maxsize: int = 100
    catchup_max_fires: int = 1000

    model_config = {"env_prefix": "SCHEDULER_"}


settings = Settings()
