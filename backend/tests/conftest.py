# backend/tests/conftest.py

import json
import os
from pathlib import Path

# Environment variables take precedence over a local .env, so set these
# before anything from app is imported. This guarantees tests can never reach
# a real database, even on a machine whose .env points at production.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DATABASE_PUBLIC_URL"] = "sqlite://"
os.environ["ADMIN_TOKEN"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200

    def json(self):
        return json.loads(self.content.decode("utf-8"))

    def raise_for_status(self):
        return None


class FakeHttp:
    """Stands in for httpx.get. Routes a URL to a fixture file by the first
    matching substring, and records every call for assertions."""

    def __init__(self, routes: dict[str, str]):
        self.routes = routes
        self.calls: list[tuple[str, dict | None]] = []

    def __call__(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        for fragment, fixture in self.routes.items():
            if fragment in url:
                return FakeResponse((FIXTURES / fixture).read_bytes())
        raise AssertionError(f"unexpected HTTP call in test: {url}")


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def refuse(url, *args, **kwargs):
        raise AssertionError(f"tests must not make network calls: {url}")

    monkeypatch.setattr(httpx, "get", refuse)


@pytest.fixture
def fake_http(monkeypatch):
    def install(routes: dict[str, str]) -> FakeHttp:
        fake = FakeHttp(routes)
        monkeypatch.setattr(httpx, "get", fake)
        return fake

    return install


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def admin_token(monkeypatch):
    def configure(value: str):
        monkeypatch.setenv("ADMIN_TOKEN", value)
        get_settings.cache_clear()

    yield configure
    get_settings.cache_clear()
