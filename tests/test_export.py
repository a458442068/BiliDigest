from src.utils.export import ExportService
from src.utils.storage import ResultStorage


def test_export_service_generates_txt_md_json(tmp_path):
    storage = ResultStorage(str(tmp_path))
    bv_id = "BV1xx411c7mD"
    storage.save_metadata(
        bv_id,
        {
            "bv_id": bv_id,
            "video": {"title": "Demo"},
            "parts": [{"part": 1, "title": "intro"}],
        },
    )
    storage.save_transcript(bv_id, 1, 1, "hello world")
    storage.save_translation(bv_id, 1, 1, "你好世界")
    storage.save_summary(
        bv_id,
        1,
        1,
        {"transcript_clean": "clean transcript", "summary": "short summary"},
    )
    service = ExportService(storage)

    assert "【文字稿】\nhello world" in service.txt(bv_id, 1)
    assert "# Demo" in service.md(bv_id, 1)
    assert service.json(bv_id, 1)["summary"] == "short summary"
