from pydantic import BaseModel, Field


class ProcessOptions(BaseModel):
    translate: bool = Field(default=False, description="是否翻译")
    summarize: bool = Field(default=False, description="是否生成摘要")
    force: bool = Field(default=False, description="是否强制重跑")


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
    summary: str | None = None
    result_dir: str | None = None
    cached_steps: list[str] = Field(default_factory=list)
