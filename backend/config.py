"""Application settings.

Typed configuration loaded from environment variables / a local .env file.
All fields have safe defaults. Nothing in the scaffold phase consumes these
beyond instantiation; later build-order phases (datasource, caching, harden)
import `settings` from here so no upstream call or path is ever hardcoded.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # populate_by_name so a field carrying a validation_alias (environment)
    # can still be set by its own name, which is how the tests pin behaviour
    # without reaching for the process environment.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore",
                                      populate_by_name=True)

    # Which deployment this is. Vercel sets VERCEL_ENV to production, preview
    # or development on its own, so a correct value needs no manual wiring;
    # ENVIRONMENT overrides it for any other host. Anything that is not
    # "development" is reachable from the internet and is treated as such.
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "VERCEL_ENV"))

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

    # Inbound rate limit, per client per window, per process. See
    # services/ratelimit.py for why "per process" is the honest wording.
    rate_limit_requests: int = 60
    rate_limit_window_secs: float = 60.0
    rate_limit_max_keys: int = 4096

    # Nothing here accepts an upload and the one POST carries no body, so this
    # is a door that starts closed rather than one widened to fit a payload.
    max_request_bytes: int = 65_536

    @property
    def is_deployed(self) -> bool:
        """Reachable from the internet, so held to the deployed rules."""
        return self.environment.strip().lower() in ("production", "preview")

    @property
    def docs_enabled(self) -> bool:
        """Swagger, ReDoc and the schema. Off wherever the public can reach it.

        They are not secret, but they are a free map of every route and
        parameter shape, and nothing on a deployed host needs them.
        """
        return not self.is_deployed

    def safe_cors_origins(self) -> list[str]:
        """The configured origins minus any that must never be served.

        Sanitised rather than fatal on purpose. A wildcard in this list is a
        real hole, but refusing to boot over it takes the whole site down for
        a value the app can simply decline to honour; dropping it fails the
        request closed and leaves the site up. Every drop is reported by
        security_problems() and logged at startup.
        """
        out: list[str] = []
        for raw in self.cors_origins:
            origin = raw.strip().rstrip("/")
            if not origin or origin == "*":
                continue
            if self.is_deployed and not origin.startswith("https://"):
                continue
            out.append(origin)
        return out

    def security_problems(self) -> list[str]:
        """Everything about this configuration that is unsafe, in plain words.

        Returned rather than raised so one bad value cannot black out a site
        whose other settings are fine. main.py logs each at ERROR on startup.
        """
        problems: list[str] = []
        raw_origins = [o.strip().rstrip("/") for o in self.cors_origins]

        if "*" in raw_origins:
            problems.append(
                'CORS_ORIGINS contains "*": a wildcard lets any site read this'
                " API in a visitor's browser. The wildcard is ignored.")
        if self.is_deployed:
            plain = [o for o in raw_origins
                     if o and o != "*" and not o.startswith("https://")]
            if plain:
                problems.append(
                    f"CORS_ORIGINS has non-HTTPS origins on a deployed host"
                    f" ({', '.join(plain)}). They are ignored.")
            if self.cache_backend != "postgres":
                problems.append(
                    "CACHE_BACKEND is not postgres on a deployed host: every"
                    " instance would keep its own cache and two of them can"
                    " quote two different prices for one part.")
        if self.recorder_token and len(self.recorder_token) < 32:
            problems.append(
                "RECORDER_TOKEN is shorter than 32 characters, which is short"
                " enough to be worth guessing. Generate one with"
                ' python -c "import secrets; print(secrets.token_urlsafe(32))".')
        if self.database_url and not any(
                marker in self.database_url for marker in ("sslmode=", "ssl=")):
            problems.append(
                "DATABASE_URL does not ask for TLS. Append ?sslmode=require so"
                " the connection cannot be downgraded.")
        return problems


settings = Settings()
