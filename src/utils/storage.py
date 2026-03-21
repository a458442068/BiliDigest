import json
import shutil
from pathlib import Path

from loguru import logger

from src.config import settings


class ResultStorage:
    def __init__(self, result_dir: str | None = None):
        self.result_dir = Path(result_dir or settings.result_dir)
        self.result_dir.mkdir(parents=True, exist_ok=True)

    def get_dir(self, bv_id: str) -> Path:
        d = self.result_dir / bv_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _prefix(self, part: int, total_parts: int) -> str:
        if total_parts > 1:
            return f"P{part}_"
        return ""

    def has_audio(self, bv_id: str, part: int, total_parts: int) -> bool:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}audio.wav").exists()

    def has_transcript(self, bv_id: str, part: int, total_parts: int) -> bool:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}transcript.txt").exists()

    def has_translation(self, bv_id: str, part: int, total_parts: int) -> bool:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}translation.txt").exists()

    def has_summary(self, bv_id: str, part: int, total_parts: int) -> bool:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}summary.txt").exists()

    def get_audio_path(self, bv_id: str, part: int, total_parts: int) -> str:
        prefix = self._prefix(part, total_parts)
        return str(self.get_dir(bv_id) / f"{prefix}audio.wav")

    def save_audio(
        self, bv_id: str, part: int, total_parts: int, audio_path: str
    ) -> str:
        prefix = self._prefix(part, total_parts)
        dest = self.get_dir(bv_id) / f"{prefix}audio.wav"
        shutil.copy2(audio_path, dest)
        logger.info(f"已保存音频: {dest}")
        return str(dest)

    def save_transcript(self, bv_id: str, part: int, total_parts: int, transcript: str):
        prefix = self._prefix(part, total_parts)
        path = self.get_dir(bv_id) / f"{prefix}transcript.txt"
        path.write_text(transcript, encoding="utf-8")
        logger.info(f"已保存文字稿: {path}")

    def save_translation(
        self, bv_id: str, part: int, total_parts: int, translation: str
    ):
        prefix = self._prefix(part, total_parts)
        path = self.get_dir(bv_id) / f"{prefix}translation.txt"
        path.write_text(translation, encoding="utf-8")
        logger.info(f"已保存翻译: {path}")

    def save_summary(self, bv_id: str, part: int, total_parts: int, summary: str):
        prefix = self._prefix(part, total_parts)
        path = self.get_dir(bv_id) / f"{prefix}summary.txt"
        path.write_text(summary, encoding="utf-8")
        logger.info(f"已保存摘要: {path}")

    def load_transcript(self, bv_id: str, part: int, total_parts: int) -> str:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}transcript.txt").read_text(
            encoding="utf-8"
        )

    def load_translation(self, bv_id: str, part: int, total_parts: int) -> str:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}translation.txt").read_text(
            encoding="utf-8"
        )

    def load_summary(self, bv_id: str, part: int, total_parts: int) -> str:
        prefix = self._prefix(part, total_parts)
        return (self.get_dir(bv_id) / f"{prefix}summary.txt").read_text(
            encoding="utf-8"
        )

    def load_metadata(self, bv_id: str) -> dict:
        path = self.get_dir(bv_id) / "metadata.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def save_metadata(self, bv_id: str, metadata: dict):
        path = self.get_dir(bv_id) / "metadata.json"
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"已更新metadata: {path}")

    def rename_old_file(
        self,
        bv_id: str,
        part: int,
        total_parts: int,
        file_type: str,
        old_model_name: str,
    ):
        prefix = self._prefix(part, total_parts)
        old_path = self.get_dir(bv_id) / f"{prefix}{file_type}.txt"
        if old_path.exists():
            safe_name = old_model_name.replace("/", "_").replace("\\", "_")
            new_path = old_path.with_name(f"{prefix}{file_type}_{safe_name}.txt")
            old_path.rename(new_path)
            logger.info(f"已重命名旧文件: {old_path} -> {new_path}")
