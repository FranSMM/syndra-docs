"""
Validation of the semantic search query. Needs no running stack: the API key
check is overridden, and a query outside its limits is rejected with 422 before
the handler reaches Redis, the embedding model or Qdrant.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import verify_api_key
from app.api.v1.endpoints.search import MAX_QUERY_LENGTH
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[verify_api_key] = lambda: SimpleNamespace(client_name="test")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("query", ["ab", "x" * (MAX_QUERY_LENGTH + 1)])
def test_query_outside_its_limits_is_rejected(client, query):
    response = client.get("/api/v1/search/semantic", params={"query": query})
    assert response.status_code == 422


def test_limit_is_published_in_the_schema():
    params = app.openapi()["paths"]["/api/v1/search/semantic"]["get"]["parameters"]
    query = next(p for p in params if p["name"] == "query")
    assert query["schema"]["maxLength"] == MAX_QUERY_LENGTH
