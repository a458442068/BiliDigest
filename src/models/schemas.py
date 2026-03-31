from pydantic import BaseModel, Field


class ProcessOptions(BaseModel):
    translate: bool = Field(default=False, description="是否翻译")
    summarize: bool = Field(default=False, description="是否生成摘要")
    force: bool = Field(default=False, description="是否强制重跑")
    from_step: str | None = Field(
        default=None, description="从指定步骤开始重跑 (stt/translation/summary)"
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


class ProgressInfo(BaseModel):
    bv_id: str
    status: str = Field(description="processing | done | error")
    current_step: str = Field(
        description="downloading | stt | translating | summarizing | done"
    )
    step_progress: float = Field(default=0.0, description="当前步骤进度 0.0~1.0")
    total_parts: int = 1
    current_part: int = 1
    error: str | None = None
