from typing import Literal

from pydantic import BaseModel, Field


class ProcessOptions(BaseModel):
    translate: bool = Field(default=False, description="是否翻译")
    summarize: bool = Field(default=False, description="是否生成摘要")
    force: bool = Field(default=False, description="是否强制重跑")
    from_step: str | None = Field(
        default=None, description="从指定步骤开始重跑 (stt/translation/summary)"
    )
    target_parts: list[int] | None = Field(
        default=None, min_length=1, description="只处理指定分P"
    )
    summary_template: Literal["general", "notes", "meeting", "study"] = Field(
        default="general", description="摘要模板"
    )


class ProcessRequest(BaseModel):
    url: str = Field(description="B站视频URL或BV号")
    options: ProcessOptions = Field(default_factory=ProcessOptions)


class ErrorDetail(BaseModel):
    stage: str = Field(description="出错阶段")
    code: str = Field(description="错误码")
    message: str = Field(description="错误信息")


class ErrorResponse(BaseModel):
    status: str = "error"
    error: ErrorDetail


class ProcessResult(BaseModel):
    url: str
    transcript: str
    language: str
    duration_seconds: float | None = None
    translation: str | None = None
    transcript_clean: str | None = None
    summary: str | None = None
    result_dir: str | None = None
    cached_steps: list[str] = Field(default_factory=list)
    parts: list[dict] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    chapters: list[dict] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    entities: list[dict] = Field(default_factory=list)
    summary_template: str = "general"


class JobSubmitResponse(BaseModel):
    job_id: str
    bv_id: str
    status: str = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    bv_id: str
    status: str = Field(description="queued | processing | done | error")
    current_step: str = Field(
        description="queued | downloading | stt | translating | summarizing | done"
    )
    step_progress: float = Field(default=0.0, description="当前步骤进度 0.0~1.0")
    total_parts: int = 1
    current_part: int = 1
    error: str | None = None
    error_detail: ErrorDetail | None = None
    result_available: bool = False


class ProgressInfo(BaseModel):
    bv_id: str
    status: str = Field(description="queued | processing | done | error")
    current_step: str = Field(
        description="queued | downloading | stt | translating | summarizing | done"
    )
    step_progress: float = Field(default=0.0, description="当前步骤进度 0.0~1.0")
    total_parts: int = 1
    current_part: int = 1
    error: str | None = None
