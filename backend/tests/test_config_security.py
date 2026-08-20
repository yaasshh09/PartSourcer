"""What the settings object refuses to hand the app, and what it reports.

The rule these lock in: an unsafe value in the environment may be *reported*,
but it must never reach the middleware that would act on it.
"""

from config import Settings


# _env_file=None so these assert on the arguments and nothing else. Without it
# a developer's own .env decides whether the suite passes.
def dev(**kwargs) -> Settings:
    return Settings(_env_file=None, environment="development", **kwargs)


def prod(**kwargs) -> Settings:
    return Settings(_env_file=None, environment="production", **kwargs)


def test_wildcard_origin_never_survives_into_the_served_list():
    s = prod(cors_origins=["*", "https://part-sourcer.vercel.app"])
    assert s.safe_cors_origins() == ["https://part-sourcer.vercel.app"]


def test_wildcard_origin_is_reported_rather_than_swallowed():
    problems = prod(cors_origins=["*"]).security_problems()
    assert any("*" in p for p in problems)


def test_plain_http_origins_are_dropped_on_a_deployed_host():
    s = prod(cors_origins=["http://part-sourcer.vercel.app",
                           "https://part-sourcer.vercel.app"])
    assert s.safe_cors_origins() == ["https://part-sourcer.vercel.app"]
    assert any("non-HTTPS" in p for p in s.security_problems())


def test_localhost_origins_still_work_in_development():
    s = dev(cors_origins=["http://localhost:5173"])
    assert s.safe_cors_origins() == ["http://localhost:5173"]
    assert s.security_problems() == []


def test_a_trailing_slash_does_not_silently_break_the_allowlist():
    """The browser never sends one, so it would be an origin that matches nothing."""
    s = prod(cors_origins=["https://part-sourcer.vercel.app/"])
    assert s.safe_cors_origins() == ["https://part-sourcer.vercel.app"]


def test_docs_are_on_in_development_and_off_everywhere_reachable():
    assert dev().docs_enabled is True
    assert Settings(_env_file=None, environment="preview").docs_enabled is False
    assert prod().docs_enabled is False


def test_vercel_env_alone_is_enough_to_mark_a_deploy(monkeypatch):
    """Vercel sets it, so a correct value needs no extra dashboard entry."""
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert Settings().is_deployed is True
    assert Settings().docs_enabled is False


def test_a_short_recorder_token_is_called_out():
    assert any("RECORDER_TOKEN" in p
               for p in dev(recorder_token="hunter2").security_problems())
    assert not any("RECORDER_TOKEN" in p for p in
                   dev(recorder_token="x" * 43).security_problems())


def test_a_database_url_that_does_not_ask_for_tls_is_called_out():
    plain = dev(database_url="postgresql://u:p@host/db")
    assert any("TLS" in p for p in plain.security_problems())
    tls = dev(database_url="postgresql://u:p@host/db?sslmode=require")
    assert not any("TLS" in p for p in tls.security_problems())


def test_a_per_instance_cache_on_a_deployed_host_is_called_out():
    """Two instances with their own cache can quote two prices for one part."""
    assert any("CACHE_BACKEND" in p
               for p in prod(cache_backend="sqlite").security_problems())


def test_a_clean_production_configuration_reports_nothing():
    s = prod(cors_origins=["https://part-sourcer.vercel.app"],
             cache_backend="postgres",
             database_url="postgresql://u:p@host/db?sslmode=require",
             recorder_token="x" * 43)
    assert s.security_problems() == []
