import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    settings = Settings(backend="local", acceptance_threshold=0.75, min_grounding_score=0.1, local_kb_dir="kb")
    with TestClient(create_app(settings)) as c:
        yield c
