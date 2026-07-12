import json
import re
import shutil
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from loguru import logger

from src.config import settings
from src.models.domain import ArtifactKind, ProcessingStep


SAFE_BV_ID_PATTERN = re.compile(r"^(BV[1-9A-HJ-NP-Za-km-z]{10}|[0-9a-f]{12})$")


class AudioDownloadTransaction:
    def __init__(
        self, storage: "ResultStorage", bv_id: str, part: int, total_parts: int
    ):
        self.storage = storage
        self.bv_id = storage.validate_bv_id(bv_id)
        self.part = part
        self.total_parts = total_parts
        self.final_path = storage.artifact_path(
            self.bv_id, part, total_parts, ArtifactKind.AUDIO
        )
        prefix = storage._prefix(part, total_parts) or "P1_"
        staging_root = storage.get_dir(self.bv_id) / ".staging"
        self.work_dir = (
            staging_root / f"download-{prefix.rstrip('_')}-{uuid4().hex}"
        )

    def __enter__(self) -> "AudioDownloadTransaction":
        self.work_dir.mkdir(parents=True, exist_ok=False)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        staging_dir = self.work_dir.parent
        try:
            staging_dir.rmdir()
        except OSError:
            pass
        return False

    def commit_audio(self, audio_path: str) -> str:
        source = Path(audio_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"音频文件不存在: {source}")
        work_dir = self.work_dir.resolve()
        if source != work_dir and work_dir not in source.parents:
            raise ValueError(f"音频文件不在下载临时目录内: {source}")

        commit_path = self.work_dir / f"{self.final_path.name}.commit"
        if source != commit_path.resolve():
            source.replace(commit_path)
        commit_path.replace(self.final_path)
        logger.info(f"已提交音频: {self.final_path}")
        return str(self.final_path)


class ResultStorage:
    def __init__(self, result_dir: str | None = None):
        self.result_dir = Path(result_dir or settings.result_dir).resolve()
        self.result_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_bv_id(bv_id: str) -> str:
        if not SAFE_BV_ID_PATTERN.fullmatch(bv_id or ""):
            raise ValueError(f"非法视频ID: {bv_id}")
        return bv_id

    def safe_video_dir(self, bv_id: str, create: bool = True) -> Path:
        safe_id = self.validate_bv_id(bv_id)
        video_dir = (self.result_dir / safe_id).resolve()
        if self.result_dir != video_dir and self.result_dir not in video_dir.parents:
            raise ValueError(f"视频目录越界: {bv_id}")
        if create:
            video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir

    def get_dir(self, bv_id: str) -> Path:
        return self.safe_video_dir(bv_id)

    def _prefix(self, part: int, total_parts: int) -> str:
        if total_parts > 1:
            return f"P{part}_"
        return ""

    def artifact_path(
        self, bv_id: str, part: int, total_parts: int, kind: ArtifactKind | str
    ) -> Path:
        kind = ArtifactKind(kind)
        filenames = {
            ArtifactKind.AUDIO: "audio.wav",
            ArtifactKind.SEGMENTS: "segments.json",
            ArtifactKind.TRANSCRIPT: "transcript.txt",
            ArtifactKind.TRANSLATION: "translation.txt",
            ArtifactKind.SUMMARY: "summary.txt",
            ArtifactKind.TRANSCRIPT_CLEAN: "transcript_clean.txt",
        }
        return (
            self.get_dir(bv_id)
            / f"{self._prefix(part, total_parts)}{filenames[kind]}"
        )

    def artifact_exists(
        self, bv_id: str, part: int, total_parts: int, kind: ArtifactKind | str
    ) -> bool:
        return self.artifact_path(bv_id, part, total_parts, kind).exists()

    def list_part_artifacts(
        self, bv_id: str, part: int, total_parts: int
    ) -> dict[str, bool]:
        return {
            kind.value: self.artifact_exists(bv_id, part, total_parts, kind)
            for kind in ArtifactKind
        }

    def load_artifact(
        self, bv_id: str, part: int, total_parts: int, kind: ArtifactKind | str
    ):
        kind = ArtifactKind(kind)
        path = self.artifact_path(bv_id, part, total_parts, kind)
        if kind == ArtifactKind.SEGMENTS:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if kind == ArtifactKind.AUDIO:
            return str(path)
        return path.read_text(encoding="utf-8")

    def save_artifact(
        self,
        bv_id: str,
        part: int,
        total_parts: int,
        kind: ArtifactKind | str,
        content,
    ):
        kind = ArtifactKind(kind)
        path = self.artifact_path(bv_id, part, total_parts, kind)
        if kind == ArtifactKind.AUDIO:
            tmp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            try:
                shutil.copy2(content, tmp_path)
                tmp_path.replace(path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
            logger.info(f"已保存音频: {path}")
            return str(path)
        if kind == ArtifactKind.SEGMENTS:
            path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
            logger.info(f"已保存时间戳: {path}")
            return path
        path.write_text(str(content), encoding="utf-8")
        logger.info(f"已保存产物 {kind.value}: {path}")
        return path

    def delete_artifacts(
        self,
        bv_id: str,
        part: int,
        total_parts: int,
        from_step: ProcessingStep | str,
    ) -> list[Path]:
        from_step = ProcessingStep(from_step)
        kinds_by_step = {
            ProcessingStep.DOWNLOAD: [
                ArtifactKind.AUDIO,
                ArtifactKind.SEGMENTS,
                ArtifactKind.TRANSCRIPT,
                ArtifactKind.TRANSLATION,
                ArtifactKind.SUMMARY,
                ArtifactKind.TRANSCRIPT_CLEAN,
            ],
            ProcessingStep.STT: [
                ArtifactKind.SEGMENTS,
                ArtifactKind.TRANSCRIPT,
                ArtifactKind.TRANSLATION,
                ArtifactKind.SUMMARY,
                ArtifactKind.TRANSCRIPT_CLEAN,
            ],
            ProcessingStep.TRANSLATION: [
                ArtifactKind.TRANSLATION,
                ArtifactKind.SUMMARY,
                ArtifactKind.TRANSCRIPT_CLEAN,
            ],
            ProcessingStep.SUMMARY: [
                ArtifactKind.SUMMARY,
                ArtifactKind.TRANSCRIPT_CLEAN,
            ],
        }
        deleted = []
        for kind in kinds_by_step[from_step]:
            path = self.artifact_path(bv_id, part, total_parts, kind)
            if path.exists():
                path.unlink()
                deleted.append(path)
        return deleted

    def has_audio(self, bv_id: str, part: int, total_parts: int) -> bool:
        return self.artifact_exists(bv_id, part, total_parts, ArtifactKind.AUDIO)

    def has_transcript(self, bv_id: str, part: int, total_parts: int) -> bool:
        return self.artifact_exists(bv_id, part, total_parts, ArtifactKind.TRANSCRIPT)

    def has_translation(self, bv_id: str, part: int, total_parts: int) -> bool:
        return self.artifact_exists(bv_id, part, total_parts, ArtifactKind.TRANSLATION)

    def has_summary(self, bv_id: str, part: int, total_parts: int) -> bool:
        return self.artifact_exists(bv_id, part, total_parts, ArtifactKind.SUMMARY)

    def get_audio_path(self, bv_id: str, part: int, total_parts: int) -> str:
        return self.load_artifact(bv_id, part, total_parts, ArtifactKind.AUDIO)

    def save_audio(
        self, bv_id: str, part: int, total_parts: int, audio_path: str
    ) -> str:
        return self.save_artifact(
            bv_id, part, total_parts, ArtifactKind.AUDIO, audio_path
        )

    @contextmanager
    def audio_download_transaction(
        self, bv_id: str, part: int, total_parts: int
    ):
        with AudioDownloadTransaction(self, bv_id, part, total_parts) as tx:
            yield tx

    def cleanup_staging(self, max_age_hours: int | None = None) -> list[Path]:
        max_age_hours = (
            settings.download_staging_ttl_hours
            if max_age_hours is None
            else max_age_hours
        )
        cutoff = time.time() - max_age_hours * 3600
        deleted = []
        if not self.result_dir.exists():
            return deleted

        staging_dirs = [
            self.result_dir / ".staging",
            *self.result_dir.glob("*/.staging"),
        ]
        for staging_dir in staging_dirs:
            if not staging_dir.is_dir():
                continue
            for child in staging_dir.iterdir():
                if not child.is_dir():
                    continue
                if child.stat().st_mtime > cutoff:
                    continue
                shutil.rmtree(child)
                deleted.append(child)
                logger.info(f"已清理下载临时目录: {child}")
            try:
                next(staging_dir.iterdir())
            except StopIteration:
                staging_dir.rmdir()
        return deleted

    def save_transcript(self, bv_id: str, part: int, total_parts: int, transcript: str):
        self.save_artifact(
            bv_id, part, total_parts, ArtifactKind.TRANSCRIPT, transcript
        )

    def has_segments(self, bv_id: str, part: int, total_parts: int) -> bool:
        return self.artifact_exists(bv_id, part, total_parts, ArtifactKind.SEGMENTS)

    def save_segments(self, bv_id: str, part: int, total_parts: int, segments: list):
        self.save_artifact(bv_id, part, total_parts, ArtifactKind.SEGMENTS, segments)

    def load_segments(self, bv_id: str, part: int, total_parts: int) -> list:
        return self.load_artifact(bv_id, part, total_parts, ArtifactKind.SEGMENTS)

    def save_translation(
        self, bv_id: str, part: int, total_parts: int, translation: str
    ):
        self.save_artifact(
            bv_id, part, total_parts, ArtifactKind.TRANSLATION, translation
        )

    def save_summary(
        self, bv_id: str, part: int, total_parts: int, summary_data: dict | str
    ):
        if isinstance(summary_data, dict):
            # Save transcript_clean
            if summary_data.get("transcript_clean"):
                self.save_artifact(
                    bv_id,
                    part,
                    total_parts,
                    ArtifactKind.TRANSCRIPT_CLEAN,
                    summary_data["transcript_clean"],
                )
            # Save summary
            if summary_data.get("summary"):
                self.save_artifact(
                    bv_id,
                    part,
                    total_parts,
                    ArtifactKind.SUMMARY,
                    summary_data["summary"],
                )
        else:
            self.save_artifact(
                bv_id, part, total_parts, ArtifactKind.SUMMARY, summary_data
            )

    def load_transcript(self, bv_id: str, part: int, total_parts: int) -> str:
        return self.load_artifact(bv_id, part, total_parts, ArtifactKind.TRANSCRIPT)

    def load_translation(self, bv_id: str, part: int, total_parts: int) -> str:
        return self.load_artifact(bv_id, part, total_parts, ArtifactKind.TRANSLATION)

    def load_summary(self, bv_id: str, part: int, total_parts: int) -> dict | str:
        summary_path = self.artifact_path(
            bv_id, part, total_parts, ArtifactKind.SUMMARY
        )
        clean_path = self.artifact_path(
            bv_id, part, total_parts, ArtifactKind.TRANSCRIPT_CLEAN
        )
        result = {}
        if clean_path.exists():
            result["transcript_clean"] = clean_path.read_text(encoding="utf-8")
        if summary_path.exists():
            result["summary"] = summary_path.read_text(encoding="utf-8")
        return result if result else ""

    def load_metadata(self, bv_id: str) -> dict:
        path = self.get_dir(bv_id) / "metadata.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def load_video_metadata(self, bv_id: str) -> dict:
        return self.load_metadata(bv_id)

    def save_metadata(self, bv_id: str, metadata: dict):
        path = self.get_dir(bv_id) / "metadata.json"
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"已更新metadata: {path}")

    def save_video_metadata(self, bv_id: str, metadata: dict):
        self.save_metadata(bv_id, metadata)

    def merge_video_metadata(self, bv_id: str, patch: dict) -> dict:
        metadata = self.load_metadata(bv_id)
        metadata.update(patch)
        self.save_metadata(bv_id, metadata)
        return metadata

    def _dir_size(self, path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @staticmethod
    def _format_size(size: int) -> str:
        units = ["B", "KB", "MB", "GB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024
        return f"{size} B"

    def list_videos(self) -> list[dict]:
        videos = []
        if not self.result_dir.exists():
            return videos
        for d in sorted(self.result_dir.iterdir()):
            if not d.is_dir():
                continue
            try:
                metadata = self.load_metadata(d.name)
            except ValueError:
                logger.warning(f"跳过非法结果目录: {d}")
                continue
            if not metadata:
                continue
            video_info = metadata.get("video", {})
            parts = metadata.get("parts", [])
            first_part = parts[0] if parts else {}
            size_bytes = self._dir_size(d)
            duration = video_info.get("duration") or sum(
                p.get("duration_seconds") or p.get("duration") or 0 for p in parts
            )
            videos.append(
                {
                    "bv_id": metadata.get("bv_id", d.name),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", "bilibili"),
                    "title": video_info.get("title", d.name),
                    "uploader": video_info.get("uploader", ""),
                    "duration": duration,
                    "language": first_part.get("language", ""),
                    "status": metadata.get("status", "done"),
                    "error": metadata.get("error"),
                    "size_bytes": size_bytes,
                    "size_label": self._format_size(size_bytes),
                    "updated_at": metadata.get("updated_at", ""),
                    "has_transcript": any(p.get("has_transcript") for p in parts),
                    "has_translation": any(p.get("has_translation") for p in parts),
                    "has_summary": any(p.get("has_summary") for p in parts),
                }
            )
        videos.sort(key=lambda v: v.get("updated_at", ""), reverse=True)
        return videos

    def delete_video(self, bv_id: str) -> bool:
        d = self.safe_video_dir(bv_id, create=False)
        if d.exists() and d.is_dir():
            shutil.rmtree(d)
            logger.info(f"已删除视频目录: {d}")
            return True
        return False

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
