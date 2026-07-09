"""Application settings.

Typed configuration loaded from environment variables / a local .env file.
All fields have safe defaults. Nothing in the scaffold phase consumes these
beyond instantiation; later build-order phases (datasource, caching, harden)
import `settings` from here so no upstream call or path is ever hardcoded.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Upstream data source (datasource phase)
    jlcsearch_base_url: str = "https://jlcsearch.tscircuit.com"
    request_timeout_secs: float = 10.0

    # Caching (caching phase): long TTL for specs, short TTL for stock/price
    specs_cache_ttl_secs: int = 2_592_000  # 30 days
    stock_cache_ttl_secs: int = 3_600      # 1 hour
    sqlite_path: str = "./partsourcer.db"

    # Hardening phase
    cors_origins: list[str] = ["*"]


settings = Settings()
