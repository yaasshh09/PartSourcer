import os

import pytest

# The app's rate limiter is one instance for the whole session, and every
# TestClient request counts against the same client key, so the suite trips
# the production limit of 60 a minute once enough API tests exist. Set before
# main is imported. The limiter itself is tested with its own tight instances
# in test_security_middleware.py.
os.environ.setdefault("RATE_LIMIT_REQUESTS", "100000")


@pytest.fixture
def anyio_backend():
    return "asyncio"
