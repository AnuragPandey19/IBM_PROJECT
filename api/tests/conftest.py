"""Pytest fixtures. Ensures DB tables exist before tests run."""
import pytest

from api.db.session import init_db


@pytest.fixture(scope="session", autouse=True)
def _initialize_db():
    """Create tables once at the start of the test session."""
    init_db()
    yield
