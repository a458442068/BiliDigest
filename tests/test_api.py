from fastapi.testclient import TestClient

from main import app
from src.api import routes as api_routes
from src.exceptions import DownloadError
from src.utils.storage import ResultStorage


client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "bili-digest"


class TestProcessEndpoint:
    def test_process_missing_url(self):
        response = client.post("/api/v1/process", json={})
        assert response.status_code == 422

    def test_process_unsupported_url(self, monkeypatch):
        async def fake_process(request):
            raise DownloadError("INVALID_URL", "不支持的链接")

        monkeypatch.setattr(api_routes.pipeline, "process_request", fake_process)

        response = client.post(
            "/api/v1/process", json={"url": "https://example.com/video/123"}
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["stage"] == "download"

    def test_process_invalid_bv(self, monkeypatch):
        async def fake_process(request):
            raise DownloadError("INVALID_URL", "不支持的链接")

        monkeypatch.setattr(api_routes.pipeline, "process_request", fake_process)

        response = client.post("/api/v1/process", json={"url": "INVALID_BV"})
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "INVALID_URL"

    def test_process_with_options(self, monkeypatch):
        captured = {}

        async def fake_process(request):
            captured["request"] = request
            return {
                "url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "transcript": "hello world",
                "language": "en",
            }

        monkeypatch.setattr(api_routes.pipeline, "process_request", fake_process)

        response = client.post(
            "/api/v1/process",
            json={
                "url": "BV1xx411c7mD",
                "options": {
                    "translate": True,
                    "summarize": True,
                    "from_step": "summary",
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["transcript"] == "hello world"
        assert captured["request"].translate is True
        assert captured["request"].summarize is True
        assert captured["request"].from_step == "summary"


class TestStatusEndpoint:
    def test_status_reads_metadata_fallback(self, monkeypatch, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"
        storage.save_metadata(
            bv_id,
            {
                "bv_id": bv_id,
                "status": "done",
                "current_step": "done",
                "step_progress": 1.0,
                "total_parts": 1,
                "parts": [{"part": 1}],
            },
        )
        monkeypatch.setattr(api_routes.pipeline, "storage", storage)
        api_routes.pipeline._progress.clear()

        response = client.get(f"/api/v1/status/{bv_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "done"
