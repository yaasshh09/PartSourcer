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
    # Nothing in the cache evicts on its own, so on a deploy with a real
    # volume it grows forever. Far longer than the offer TTL on purpose: the
    # offers table doubles as the SKU index behind the legacy C-code redirect.
    cache_prune_after_days: int = 7
    sqlite_path: str = "./partsourcer.db"

    # Where the cache lives. "sqlite" is right for local work and for any host
    # that runs exactly one always-on process. "postgres" is required anywhere
    # the app runs as several, because two processes with their own SQLite
    # file can serve two different prices for one part and each counts its own
    # upstream calls. Choosing postgres requires database_url; a silent
    # fallback to sqlite would reintroduce exactly the bug this setting exists
    # to prevent, so a missing DSN is a startup failure instead.
    cache_backend: str = "sqlite"

    # Hardening phase
    # Dev default; production Vercel origin(s) supplied via CORS_ORIGINS env.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Max one forced ?refresh=true upstream hit per key per this window.
    refresh_cooldown_secs: float = 10.0

    # History recorder (SP2a). All optional: unset means the recorder is off
    # and POST /api/internal/record returns 503.
    database_url: str | None = None
    recorder_token: str | None = None
    recorder_batch_size: int = 500
    recorder_concurrency: int = 4

    # Distributors (SP1). Unset credentials mean the distributor reports
    # state="disabled" and is never called. No new vars = today's behaviour.
    mouser_api_key: str | None = None
    digikey_client_id: str | None = None
    digikey_client_secret: str | None = None
    digikey_base_url: str = "https://api.digikey.com"
    mouser_base_url: str = "https://api.mouser.com"
    distributor_timeout_secs: float = 8.0

    # Per-distributor daily call ceilings. None means unlimited, which is what
    # jlcsearch gets: it is a free community service with no published quota,
    # and inventing a number would be a fake limit. These are config rather
    # than code so a wrong value is a dashboard edit, not a deploy.
    mouser_daily_limit: int | None = 1000
    digikey_daily_limit: int | None = 1000


settings = Settings()
