import asyncio
from pathlib import Path

from src.exceptions import DownloadError
from src.services.pipeline import ProcessingPipeline
from src.utils.storage import ResultStorage


class FakeDownloader:
    def __init__(self, audio_path: Path | None = None, fail_download: bool = False):
        self.audio_path = audio_path
        self.fail_download = fail_download

    def get_video_info(self, url: str) -> dict:
        return {"title": "Demo", "uploader": "Tester", "duration": 12}

    def download(self, url: str, part: int = 1) -> str:
        if self.fail_download:
            raise DownloadError("DOWNLOAD_FAILED", "fake failure")
        return str(self.audio_path)


class FakeSTT:
    def transcribe(self, audio_path: str) -> dict:
        return {
            "transcript": "hello world",
            "language": "en",
            "duration_seconds": 12.0,
        }


class FakeTranslator:
    async def translate(self, text: str, source_lang: str) -> str:
        return "你好世界"


class FakeSummarizer:
    async def summarize(self, text: str) -> dict:
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
    assert metadata["parts"][0]["has_transcript"] is True
    assert metadata["parts"][0]["has_translation"] is True
    assert metadata["parts"][0]["has_summary"] is True


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
