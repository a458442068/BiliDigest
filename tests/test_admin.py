from fastapi.testclient import TestClient

from main import app
from src.admin import routes as admin_routes
from src.api import routes as api_routes
from src.utils.storage import ResultStorage


client = TestClient(app)


def seed_video(
    storage: ResultStorage,
    bv_id: str = "BV1xx411c7mD",
    title: str = "a&b demo",
    uploader: str = "tester",
    source: str = "bilibili",
    language: str = "en",
    status: str = "done",
    has_translation: bool = True,
    has_summary: bool = True,
):
    metadata = {
        "bv_id": bv_id,
        "url": f"https://www.bilibili.com/video/{bv_id}",
        "source": source,
        "status": status,
        "updated_at": "2026-03-21T10:30:00",
        "video": {"title": title, "uploader": uploader, "duration": 12},
        "parts": [
            {
                "part": 1,
                "title": "intro",
                "duration_seconds": 12,
                "language": language,
                "has_audio": True,
                "has_transcript": True,
                "has_translation": has_translation,
                "has_summary": has_summary,
            }
        ],
    }
    storage.save_metadata(bv_id, metadata)
    storage.save_transcript(bv_id, 1, 1, "hello world")
    if has_translation:
        storage.save_translation(bv_id, 1, 1, "你好世界")
    if has_summary:
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


def test_admin_list_filters_stats_and_encodes_params(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    seed_video(storage)
    seed_video(
        storage,
        bv_id="abcdef123456",
        title="another video",
        uploader="other",
        source="local",
        language="zh",
        status="error",
        has_translation=False,
        has_summary=False,
    )

    response = client.get(
        "/admin/?q=a%26b&status=done&source=bilibili&language=en&artifact=summary&sort=source&order=asc"
    )

    assert response.status_code == 200
    assert "视频处理工作台" in response.text
    assert "总占用空间" in response.text
    assert "已筛选 1 / 2 个视频" in response.text
    assert 'name="sort" value="source"' in response.text
    assert "q=a%26b" in response.text
    assert "artifact=summary" in response.text
    assert "a&amp;b demo" in response.text
    assert "another video" not in response.text


def test_admin_list_empty_filter_state(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    seed_video(storage)

    response = client.get("/admin/?status=error")

    assert response.status_code == 200
    assert "没有匹配当前筛选的视频" in response.text
    assert "清空筛选" in response.text


def test_admin_detail_shows_part_metadata(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)

    response = client.get(f"/admin/video/{bv_id}")

    assert response.status_code == 200
    assert "P1 intro" in response.text
    assert "分P导航" in response.text
    assert "视频信息" in response.text
    assert "TXT" in response.text
    assert "复制" in response.text
    assert "展开" in response.text
    assert "刷新信息" in response.text
    assert "重跑当前P" in response.text
    assert "setInterval" in response.text
    assert "x-data" not in response.text
    assert 'data-part-content="1" class=""' in response.text
    assert 'data-part-panel="1" data-tab-panel="summary" class=""' in response.text
    assert "12秒" in response.text


def test_admin_detail_shows_timestamp_controls(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)
    storage.save_segments(
        bv_id,
        1,
        1,
        [
            {"text": "hello ", "start": 0.0, "end": 0.4},
            {"text": "world", "start": 0.4, "end": 1.2},
        ],
    )

    response = client.get(f"/admin/video/{bv_id}")

    assert response.status_code == 200
    assert "时间轴文字稿" in response.text
    assert 'data-segment-start="0.0"' in response.text
    assert "setActiveSegment" in response.text


def test_admin_detail_shows_auto_polling_for_processing_video(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage, status="processing")
    admin_routes.pipeline.mark_queued(bv_id)

    response = client.get(f"/admin/video/{bv_id}")

    assert response.status_code == 200
    assert "自动更新中" in response.text
    assert "语音识别" in response.text


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


def test_refresh_metadata_uses_explicit_admin_action(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = seed_video(storage)
    captured = {}

    def fake_refresh(target_bv_id):
        captured["bv_id"] = target_bv_id
        return storage.load_metadata(target_bv_id)

    monkeypatch.setattr(admin_routes.pipeline, "refresh_metadata", fake_refresh)

    response = client.post(
        f"/admin/video/{bv_id}/refresh-metadata", follow_redirects=False
    )

    assert response.status_code == 303
    assert captured["bv_id"] == bv_id
    assert storage.load_metadata(bv_id)["status"] == "done"


def test_reprocess_part_deletes_only_selected_part_artifacts(monkeypatch, tmp_path):
    storage = patch_storage(monkeypatch, tmp_path)
    bv_id = "BV1xx411c7mD"
    storage.save_metadata(
        bv_id,
        {
            "bv_id": bv_id,
            "url": f"https://www.bilibili.com/video/{bv_id}",
            "status": "done",
            "parts": [{"part": 1}, {"part": 2}],
        },
    )
    storage.save_transcript(bv_id, 1, 2, "p1 transcript")
    storage.save_transcript(bv_id, 2, 2, "p2 transcript")

    async def fake_process(request):
        return {}

    monkeypatch.setattr(admin_routes.pipeline, "process_request", fake_process)

    response = client.post(
        f"/admin/video/{bv_id}/reprocess/stt?part=1", follow_redirects=False
    )

    assert response.status_code == 303
    assert storage.has_transcript(bv_id, 1, 2) is False
    assert storage.has_transcript(bv_id, 2, 2) is True


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
