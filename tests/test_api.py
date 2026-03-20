import pytest
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "stt-server"


class TestProcessEndpoint:
    def test_process_missing_url(self):
        response = client.post("/api/v1/process", json={})
        assert response.status_code == 422

    def test_process_invalid_url(self):
        response = client.post(
            "/api/v1/process", json={"url": "https://youtube.com/watch?v=123"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["stage"] == "download"

    def test_process_invalid_bv(self):
        response = client.post("/api/v1/process", json={"url": "INVALID_BV"})
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["stage"] == "download"

    def test_process_with_options(self):
        response = client.post(
            "/api/v1/process",
            json={
                "url": "BV1xx411c7mD",
                "options": {"translate": True, "summarize": True},
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["stage"] == "download"
