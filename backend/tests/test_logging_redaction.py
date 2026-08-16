"""Secrets in request URLs must not reach the logs.

Mouser takes its API key as a query parameter, and httpx logs every request
line, URL and all, at INFO. Root is configured at INFO, so the key was being
written to the application log verbatim, which on a hosted backend means the
provider's log stream. The service layer already refuses to put an exception
message into a status detail for exactly this reason; that care is worth
nothing if the HTTP client narrates the same secret one line earlier.
"""

import logging

import httpx

import main  # noqa: F401  imported for the logging configuration it applies

SECRET = "not-a-real-key-6f2a9c"


def test_a_secret_in_a_request_url_never_reaches_the_logs(caplog):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))

    with caplog.at_level(logging.INFO):
        with httpx.Client(transport=transport) as client:
            client.get(f"https://api.mouser.com/api/v1/search/keyword?apiKey={SECRET}")

    assert SECRET not in caplog.text


def test_httpx_can_still_report_a_real_problem(caplog):
    """Silencing the request line must not silence genuine failures, or the
    fix trades a leak for a blind spot."""
    logging.getLogger("httpx").warning("connection pool exhausted")
    assert "connection pool exhausted" in caplog.text
