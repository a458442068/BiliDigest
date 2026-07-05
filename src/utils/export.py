from dataclasses import dataclass

from src.models.domain import ArtifactKind
from src.utils.storage import ResultStorage
from src.utils.subtitle import (
    segments_to_srt,
    segments_to_vtt,
    transcript_to_srt,
    transcript_to_vtt,
)


class ExportError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ExportNotFound(ExportError):
    status_code = 404


class InvalidExportPart(ExportError):
    status_code = 400


@dataclass
class ExportContext:
    bv_id: str
    part: int
    total_parts: int
    metadata: dict


class ExportService:
    def __init__(self, storage: ResultStorage | None = None):
        self.storage = storage or ResultStorage()

    def load_context(self, bv_id: str, part: int) -> ExportContext:
        try:
            metadata = self.storage.load_metadata(bv_id)
        except ValueError as e:
            raise InvalidExportPart(str(e)) from e
        if not metadata:
            raise ExportNotFound("视频不存在")

        total_parts = len(metadata.get("parts", [])) or 1
        if part < 1 or part > total_parts:
            raise InvalidExportPart(f"分P不存在: {part}")

        return ExportContext(
            bv_id=bv_id,
            part=part,
            total_parts=total_parts,
            metadata=metadata,
        )

    def part_metadata(self, context: ExportContext) -> dict:
        return next(
            (
                p
                for p in context.metadata.get("parts", [])
                if p.get("part") == context.part
            ),
            {},
        )

    def part_texts(self, context: ExportContext) -> dict:
        def read_or_none(kind: ArtifactKind):
            try:
                return self.storage.load_artifact(
                    context.bv_id, context.part, context.total_parts, kind
                )
            except FileNotFoundError:
                return None

        return {
            "transcript": read_or_none(ArtifactKind.TRANSCRIPT),
            "translation": read_or_none(ArtifactKind.TRANSLATION),
            "transcript_clean": read_or_none(ArtifactKind.TRANSCRIPT_CLEAN),
            "summary": read_or_none(ArtifactKind.SUMMARY),
        }

    def srt(self, bv_id: str, part: int) -> str:
        context = self.load_context(bv_id, part)
        segments = self.storage.load_artifact(
            bv_id, part, context.total_parts, ArtifactKind.SEGMENTS
        )
        if segments:
            content = segments_to_srt(segments)
        else:
            try:
                transcript = self.storage.load_artifact(
                    bv_id, part, context.total_parts, ArtifactKind.TRANSCRIPT
                )
            except FileNotFoundError as e:
                raise ExportNotFound("无可用字幕数据") from e
            duration = self.part_metadata(context).get("duration_seconds", 0) or 0
            content = transcript_to_srt(transcript, duration)

        if not content:
            raise ExportNotFound("无可用字幕数据")
        return content

    def vtt(self, bv_id: str, part: int) -> str:
        context = self.load_context(bv_id, part)
        segments = self.storage.load_artifact(
            bv_id, part, context.total_parts, ArtifactKind.SEGMENTS
        )
        if segments:
            content = segments_to_vtt(segments)
        else:
            try:
                transcript = self.storage.load_artifact(
                    bv_id, part, context.total_parts, ArtifactKind.TRANSCRIPT
                )
            except FileNotFoundError as e:
                raise ExportNotFound("无可用字幕数据") from e
            duration = self.part_metadata(context).get("duration_seconds", 0) or 0
            content = transcript_to_vtt(transcript, duration)

        if not content:
            raise ExportNotFound("无可用字幕数据")
        return content

    def txt(self, bv_id: str, part: int) -> str:
        context = self.load_context(bv_id, part)
        texts = self.part_texts(context)
        part_meta = self.part_metadata(context)
        sections = [
            ("标题", context.metadata.get("video", {}).get("title") or bv_id),
            ("分P", str(part_meta.get("title") or part)),
            ("文字稿", texts.get("transcript")),
            ("翻译", texts.get("translation")),
            ("整理版", texts.get("transcript_clean")),
            ("摘要", texts.get("summary")),
        ]
        content = "\n\n".join(
            f"【{title}】\n{body}" for title, body in sections if body
        )
        if not content:
            raise ExportNotFound("无可导出内容")
        return content

    def md(self, bv_id: str, part: int) -> str:
        context = self.load_context(bv_id, part)
        texts = self.part_texts(context)
        title = context.metadata.get("video", {}).get("title") or bv_id
        part_meta = self.part_metadata(context)
        lines = [f"# {title}", "", f"- 分P: {part_meta.get('title') or part}"]
        for heading, body in (
            ("文字稿", texts.get("transcript")),
            ("翻译", texts.get("translation")),
            ("整理版", texts.get("transcript_clean")),
            ("摘要", texts.get("summary")),
        ):
            if body:
                lines.extend(["", f"## {heading}", "", body])
        content = "\n".join(lines).strip()
        if not content:
            raise ExportNotFound("无可导出内容")
        return content

    def json(self, bv_id: str, part: int) -> dict:
        context = self.load_context(bv_id, part)
        return {
            "bv_id": bv_id,
            "part": part,
            "metadata": context.metadata,
            "part_metadata": self.part_metadata(context),
            **self.part_texts(context),
        }
