import asyncio
from pathlib import Path

from src.exceptions import DownloadError
from src.services import pipeline as pipeline_module
from src.services.pipeline import ProcessingPipeline
from src.utils.bv import PartInfo
from src.utils.storage import ResultStorage


class FakeDownloader:
    def __init__(self, audio_path: Path | None = None, fail_download: bool = False):
        self.audio_path = audio_path
        self.fail_download = fail_download
        self.downloaded_parts = []
        self.probe_calls = 0

    def probe_video(self, url: str) -> dict:
        self.probe_calls += 1
        return {
            "video": {"title": "Demo", "uploader": "Tester", "duration": 12},
            "parts": [PartInfo(part=1, title="P1", duration=12)],
            "metadata_probe": {
                "logic_version": 2,
                "extractor": "yt-dlp",
                "status": "ok",
                "warnings": [],
            },
        }

    def get_video_info(self, url: str) -> dict:
        return {"title": "Demo", "uploader": "Tester", "duration": 12}

    def download(self, url: str, part: int = 1, output_dir: str | None = None) -> str:
        if self.fail_download:
            raise DownloadError("DOWNLOAD_FAILED", "fake failure")
        self.downloaded_parts.append(part)
        if output_dir:
            staged_path = Path(output_dir) / f"part{part}.wav"
            staged_path.write_bytes(self.audio_path.read_bytes())
            return str(staged_path)
        return str(self.audio_path)


class FakeSTT:
    def __init__(self):
        self.calls = 0

    def transcribe(self, audio_path: str) -> dict:
        self.calls += 1
        return {
            "transcript": "hello world",
            "language": "en",
            "duration_seconds": 12.0,
        }


class FakeTranslator:
    def __init__(self):
        self.calls = 0

    async def translate(self, text: str, source_lang: str) -> str:
        self.calls += 1
        return "你好世界"


class FakeSummarizer:
    def __init__(self):
        self.calls = 0

    async def summarize(self, text: str) -> dict:
        self.calls += 1
        return {"transcript_clean": text, "summary": "summary"}


def build_pipeline(tmp_path: Path, fail_download: bool = False) -> ProcessingPipeline:
    audio_path = tmp_path / "source.wav"
    audio_path.write_bytes(b"fake audio")

    pipeline = ProcessingPipeline()
    pipeline.storage = ResultStorage(str(tmp_path / "results"))
    pipeline.downloader = FakeDownloader(audio_path, fail_download=fail_download)
    pipeline.stt = FakeSTT()
    pipeline.translator = FakeTranslator()
    pipeline.summarizer = FakeSummarizer()
    return pipeline


def test_mark_queued_persists_metadata_progress(tmp_path):
    pipeline = build_pipeline(tmp_path)

    pipeline.mark_queued("BV1xx411c7mD", total_parts=2)
    pipeline._progress.clear()

    progress = pipeline.get_progress("BV1xx411c7mD")

    assert progress is not None
    assert progress.status == "queued"
    assert progress.current_step == "queued"
    assert progress.total_parts == 2


def test_process_persists_done_status(tmp_path):
    pipeline = build_pipeline(tmp_path)

    result = asyncio.run(pipeline.process("BV1xx411c7mD", translate=True, summarize=True))
    metadata = pipeline.storage.load_metadata("BV1xx411c7mD")

    assert result["transcript"] == "hello world"
    assert metadata["status"] == "done"
    assert metadata["current_step"] == "done"
    assert metadata["step_progress"] == 1.0
    assert metadata["metadata_logic_version"] == 2
    assert metadata["metadata_probe"]["status"] == "ok"
    assert metadata["parts"][0]["title"] == "P1"
    assert metadata["parts"][0]["duration_seconds"] == 12
    assert metadata["parts"][0]["has_transcript"] is True
    assert metadata["parts"][0]["has_translation"] is True
    assert metadata["parts"][0]["has_summary"] is True
    assert not (tmp_path / "results" / "BV1xx411c7mD" / ".staging").exists()
    assert "BV1xx411c7mD" not in pipeline._progress
    assert pipeline.get_progress("BV1xx411c7mD").status == "done"


def test_process_persists_error_status(tmp_path):
    pipeline = build_pipeline(tmp_path, fail_download=True)

    try:
        asyncio.run(pipeline.process("BV1xx411c7mD"))
    except Exception:
        pass

    metadata = pipeline.storage.load_metadata("BV1xx411c7mD")

    assert metadata["status"] == "error"
    assert metadata["current_step"] == "download"
    assert metadata["error"] == "fake failure"
    assert "BV1xx411c7mD" not in pipeline._progress
    assert pipeline.get_progress("BV1xx411c7mD").status == "error"


def test_process_target_parts_only_reprocesses_selected_part(monkeypatch, tmp_path):
    pipeline = build_pipeline(tmp_path)
    bv_id = "BV1xx411c7mD"
    pipeline.storage.save_metadata(
        bv_id,
        {
            "bv_id": bv_id,
            "url": f"https://www.bilibili.com/video/{bv_id}",
            "parts": [
                {"part": 1, "title": "P1", "language": "en"},
                {
                    "part": 2,
                    "title": "P2",
                    "language": "zh",
                    "has_transcript": True,
                    "has_translation": True,
                    "has_summary": True,
                },
            ],
        },
    )
    monkeypatch.setattr(
        pipeline_module,
        "get_parts",
        lambda url: [
            PartInfo(part=1, title="P1", duration=12),
            PartInfo(part=2, title="P2", duration=34),
        ],
    )

    asyncio.run(
        pipeline.process(
            f"https://www.bilibili.com/video/{bv_id}",
            translate=True,
            summarize=True,
            target_parts={1},
        )
    )
    metadata = pipeline.storage.load_metadata(bv_id)

    assert pipeline.downloader.downloaded_parts == [1]
    assert pipeline.stt.calls == 1
    assert metadata["parts"][0]["part"] == 1
    assert metadata["parts"][0]["has_transcript"] is True
    assert metadata["parts"][1]["part"] == 2
    assert metadata["parts"][1]["language"] == "zh"
    assert metadata["parts"][1]["has_summary"] is True
    assert pipeline.downloader.probe_calls == 0


def test_process_from_summary_uses_existing_text_without_upstream_steps(
    monkeypatch, tmp_path
):
    pipeline = build_pipeline(tmp_path)
    bv_id = "BV1xx411c7mD"
    pipeline.storage.save_metadata(
        bv_id,
        {
            "bv_id": bv_id,
            "url": f"https://www.bilibili.com/video/{bv_id}",
            "parts": [{"part": 1, "title": "P1", "language": "en"}],
        },
    )
    pipeline.storage.save_transcript(bv_id, 1, 1, "hello world")
    pipeline.storage.save_translation(bv_id, 1, 1, "你好世界")
    monkeypatch.setattr(
        pipeline_module,
        "get_parts",
        lambda url: [PartInfo(part=1, title="P1", duration=12)],
    )

    asyncio.run(
        pipeline.process(
            f"https://www.bilibili.com/video/{bv_id}",
            translate=True,
            summarize=True,
            from_step="summary",
        )
    )

    assert pipeline.downloader.downloaded_parts == []
    assert pipeline.downloader.probe_calls == 0
    assert pipeline.stt.calls == 0
    assert pipeline.translator.calls == 0
    assert pipeline.summarizer.calls == 1
    assert pipeline.storage.load_summary(bv_id, 1, 1)["summary"] == "summary"


def test_refresh_metadata_preserves_existing_when_probe_returns_empty(
    monkeypatch, tmp_path
):
    pipeline = build_pipeline(tmp_path)
    bv_id = "BV1xx411c7mD"
    pipeline.storage.save_metadata(
        bv_id,
        {
            "bv_id": bv_id,
            "url": f"https://www.bilibili.com/video/{bv_id}",
            "video": {"title": "Old title", "uploader": "Old uploader"},
            "total_parts": 2,
            "parts": [
                {"part": 1, "title": "Old P1", "duration_seconds": 12},
                {"part": 2, "title": "Old P2", "duration_seconds": 34},
            ],
        },
    )

    monkeypatch.setattr(
        pipeline,
        "_probe_video",
        lambda url: (
            {},
            [PartInfo(part=1, title="", duration=None)],
            {
                "logic_version": 2,
                "extractor": "yt-dlp",
                "status": "warning",
                "warnings": ["gone"],
            },
        ),
    )

    metadata = pipeline.refresh_metadata(bv_id)

    assert metadata["video"]["title"] == "Old title"
    assert metadata["total_parts"] == 2
    assert [part["title"] for part in metadata["parts"]] == ["Old P1", "Old P2"]
    assert metadata["metadata_probe"]["status"] == "warning"
