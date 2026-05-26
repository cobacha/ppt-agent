"""Integration tests for FastAPI endpoints."""

import os
from unittest.mock import patch, MagicMock

import pytest

# Set dummy env var before importing app (PPTAgent needs ANTHROPIC_API_KEY)
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy-key")


@pytest.fixture
def client():
    """Create TestClient with mocked PPTAgent initialization."""
    with patch("main.PPTAgent") as MockAgent:
        mock_instance = MagicMock()
        MockAgent.return_value = mock_instance

        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_has_expected_fields(self, client):
        data = client.get("/api/health").json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "model" in data
        assert "version" in data
        assert "api_key_configured" in data


class TestStylesEndpoint:
    def test_styles_returns_200(self, client):
        resp = client.get("/api/styles")
        assert resp.status_code == 200

    def test_styles_has_presets_list(self, client):
        data = client.get("/api/styles").json()
        assert "presets" in data
        assert isinstance(data["presets"], list)


class TestLayoutsEndpoint:
    def test_layouts_returns_200(self, client):
        resp = client.get("/api/layouts")
        assert resp.status_code == 200

    def test_layouts_has_layouts_field(self, client):
        data = client.get("/api/layouts").json()
        assert "layouts" in data


class TestValidateEndpoint:
    def test_validate_returns_score(self, client):
        html = '<section style="height:100vh;overflow:hidden;"><h1 style="font-size:clamp(1rem,2vw,2rem)">Hi</h1></section>'
        resp = client.post("/api/validate", json={"html": html})
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "passed" in data
        assert "issues" in data
        assert isinstance(data["score"], (int, float))


class TestOutlineEndpoint:
    def test_empty_content_returns_422(self, client):
        resp = client.post("/api/outline", json={"content": ""})
        assert resp.status_code == 422

    def test_whitespace_only_returns_422(self, client):
        resp = client.post("/api/outline", json={"content": "   \n  "})
        assert resp.status_code == 422
