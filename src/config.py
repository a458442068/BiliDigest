from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    bilibili_cookie: str = Field(default="", description="B站Cookie")
    qwen_asr_model_path: str = Field(
        default="Qwen/Qwen3-ASR-1.7B", description="Qwen ASR模型路径"
    )
    llm_provider: str = Field(default="openai", description="LLM后端")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", description="OpenAI Base URL"
    )
    llm_model: str = Field(default="gpt-4o-mini", description="LLM模型名称")
    port: int = Field(default=8000, description="服务端口")
    log_level: str = Field(default="info", description="日志级别")
    result_dir: str = Field(default="./results", description="结果保存目录")
    download_staging_ttl_hours: int = Field(
        default=72, description="下载临时目录保留时长(小时)"
    )
    stt_backend: str = Field(
        default="default", description="STT后端 (default/local/remote)"
    )
    stt_api_url: str = Field(default="", description="远程STT URL")
    stt_api_key: str = Field(default="", description="远程STT API Key")
    stt_chunk_duration: int = Field(
        default=0, description="STT分块时长(秒)，0=使用模型默认"
    )
    stt_timestamps: bool = Field(
        default=False, description="启用时间戳（需加载对齐模型）"
    )
    forced_aligner_path: str = Field(
        default="Qwen/Qwen3-ForcedAligner-0.6B", description="对齐模型路径"
    )
    stt_compile: bool = Field(
        default=False, description="启用torch.compile (对generate()模式无效，勿开启)"
    )
    stt_compile_mode: str = Field(
        default="reduce-overhead",
        description="torch.compile模式 (default/reduce-overhead/max-autotune)",
    )


settings = Settings()
