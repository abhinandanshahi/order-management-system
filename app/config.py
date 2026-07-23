from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


CsvList = Annotated[list[str], BeforeValidator(_split_csv)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Order Management System"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str

    broker_min_delay_seconds: float = Field(default=0.2, ge=0)
    broker_max_delay_seconds: float = Field(default=0.8, ge=0)
    broker_random_seed: int = 42

    day_order_expiry_seconds: int = Field(default=300, gt=0)
    day_order_scan_interval_seconds: float = Field(default=1.0, gt=0)

    market_data_enabled: bool = False
    market_data_url: str | None = None
    market_data_symbols: CsvList = Field(default_factory=list)
    market_data_reconnect_seconds: float = Field(default=5.0, gt=0)

    cors_origins: CsvList = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
