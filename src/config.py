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
    port: int = Field(default=8000, description="服务端口")
    log_level: str = Field(default="info", description="日志级别")


settings = Settings()
