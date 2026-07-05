from dataclasses import dataclass
from enum import StrEnum

from src.utils.bv import extract_video_id, get_source_name, validate_input


class ArtifactKind(StrEnum):
    AUDIO = "audio"
    SEGMENTS = "segments"
    TRANSCRIPT = "transcript"
    TRANSLATION = "translation"
    SUMMARY = "summary"
    TRANSCRIPT_CLEAN = "transcript_clean"


class ProcessingState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class ProcessingStep(StrEnum):
    DOWNLOAD = "download"
    STT = "stt"
    TRANSLATION = "translation"
    SUMMARY = "summary"


@dataclass(frozen=True)
class VideoRef:
    bv_id: str
    url: str
    source: str

    @classmethod
    def from_input(cls, url_or_id: str) -> "VideoRef":
        url = validate_input(url_or_id)
        return cls(
            bv_id=extract_video_id(url_or_id),
            url=url,
            source=get_source_name(url),
        )


@dataclass(frozen=True)
class PartMetadata:
    part: int
    title: str = ""
    duration_seconds: float | None = None
    language: str | None = None
    has_audio: bool = False
    has_transcript: bool = False
    has_translation: bool = False
    has_summary: bool = False


@dataclass(frozen=True)
class VideoMetadata:
    bv_id: str
    url: str
    source: str
    total_parts: int
    status: ProcessingState
    parts: tuple[PartMetadata, ...] = ()


@dataclass(frozen=True)
class ProcessingRequest:
    url: str
    target_parts: set[int] | None = None
    from_step: ProcessingStep | None = None
    force: bool = False
    translate: bool = False
    summarize: bool = False

    def __post_init__(self):
        if isinstance(self.from_step, str):
            object.__setattr__(self, "from_step", ProcessingStep(self.from_step))
        if self.target_parts is not None:
            object.__setattr__(self, "target_parts", set(self.target_parts))


@dataclass(frozen=True)
class StepResult:
    step: ProcessingStep
    part: int
    cached: bool
    data: dict
