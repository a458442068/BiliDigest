from fastapi.testclient import TestClient

from main import app
from src.admin import routes as admin_routes
from src.api import routes as api_routes
from src.utils.storage import ResultStorage


client = TestClient(app)


def seed_video(storage: ResultStorage):
    bv_id = "BV1xx411c7mD"
    metadata = {
        "bv_id": bv_id,
        "url": f"https://www.bilibili.com/video/{bv_id}",
        "source": "bilibili",
        "status": "done",
        "video": {"title": "a&b demo", "uploader": "tester", "duration": 12},
        "parts": [
            {
                "part": 1,
                "title": "intro",
                "duration_seconds": 12,
                "language": "en",
                "has_audio": True,
                "has_transcript": True,
                "has_translation": True,
                "has_summary": True,
            }
        ],
    }
    storage.save_metadata(bv_id, metadata)
    storage.save_transcript(bv_id, 1, 1, "hello world")
    storage.save_translation(bv_id, 1, 1, "你好世界")
    storage.save_summary(
        bv_id,
        1,
        1,
        {"transcript_clean": "hello world", "summary": "summary"},
    )
    return bv_id


def patch_storage(monkeypatch, tmp_path):
    storage = ResultStorage(str(tmp_path))
    monkeypatch.setattr(admin_routes, "storage", storage)
    monkeypatch.setattr(admin_routes.pipeline, "storage", storage)
    monkeypatch.setattr(api_routes.export_service, "storage", storage)
    admin_routes.pipeline._progress.clear()
    return storage


def test_admin_list_encodes_search_and_sorts_source(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    seed_video(storage)

    response = client.get("/admin/?q=a%26b&sort=source&order=asc")

    assert response.status_code == 200
    assert "sort=source" in response.text
    assert "q=a%26b" in response.text
    assert "a&amp;b demo" in response.text


def test_admin_detail_shows_part_metadata(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)

    response = client.get(f"/admin/video/{bv_id}")

    assert response.status_code == 200
    assert "P1 intro" in response.text
    assert "下载 TXT" in response.text
    assert "重跑本P" in response.text
    assert "刷新状态" in response.text
    assert "setInterval" not in response.text


def test_reprocess_part_marks_queued_without_real_pipeline(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)
    captured = {}

    async def fake_process(request):
        captured["request"] = request
        return {}

    monkeypatch.setattr(admin_routes.pipeline, "process_request", fake_process)

    response = client.post(
        f"/admin/video/{bv_id}/reprocess/stt?part=1", follow_redirects=False
    )

    assert response.status_code == 303
    assert storage.load_metadata(bv_id)["status"] == "queued"
    assert captured["request"].target_parts == {1}
    assert captured["request"].from_step == "stt"


def test_delete_video_clears_stale_progress(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)
    admin_routes.pipeline.mark_queued(bv_id)

    response = client.post(f"/admin/video/{bv_id}/delete", follow_redirects=False)
    status_response = client.get(f"/api/v1/status/{bv_id}")

    assert response.status_code == 303
    assert status_response.status_code == 404
    assert admin_routes.pipeline.get_progress(bv_id) is None


def test_export_txt_md_json(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)

    txt = client.get(f"/api/v1/export/{bv_id}/txt")
    md = client.get(f"/api/v1/export/{bv_id}/md")
    json_response = client.get(f"/api/v1/export/{bv_id}/json")

    assert txt.status_code == 200
    assert "hello world" in txt.text
    assert md.status_code == 200
    assert "# a&b demo" in md.text
    assert json_response.status_code == 200
    assert json_response.json()["transcript"] == "hello world"
