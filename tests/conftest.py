import os
import tempfile

# Settings are read at import time, so configure the environment before importing the app.
os.environ.update(
    {
        "GROQ_API_KEY": "test-key",
        "API_KEYS": "valid-key-1,valid-key-2",
        "CORS_ORIGINS": "https://sohamchaudhari.in",
        "RATE_LIMIT_DATA": "3/minute",
        "RATE_LIMIT_CHAT": "2/minute",
        "CHECKPOINT_DB": os.path.join(tempfile.mkdtemp(), "checkpoints.sqlite"),
    }
)

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.security import limiter


@pytest.fixture
def client():
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth():
    return {"X-API-Key": "valid-key-1"}
