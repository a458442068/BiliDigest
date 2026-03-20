import httpx
from loguru import logger

from src.config import settings
from src.exceptions import SummarizationError


class Summarizer:
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，摘要功能将不可用")

    def summarize(self, text: str) -> str | None:
        if not text or len(text.strip()) < 10:
            logger.warning("文本内容过短，跳过摘要")
            return None

        if not settings.openai_api_key:
            raise SummarizationError("LLM_API_ERROR", "OPENAI_API_KEY 未配置")

        logger.info("调用LLM API生成摘要")
        try:
            summary = self._call_llm(text)
            summary = self._strip_thinking(summary)
            logger.info("摘要生成完成")
            return summary
        except SummarizationError:
            raise
        except Exception as e:
            raise SummarizationError("LLM_API_ERROR", f"摘要API调用失败: {e}")

    def _call_llm(self, text: str) -> str:
        url = f"{settings.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的文本摘要助手。请为以下文字稿生成简洁的中文摘要，涵盖主要观点和关键信息。摘要长度适中，不宜过长或过短。只返回摘要内容，不要添加任何解释。",
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise SummarizationError(
                    "LLM_API_ERROR",
                    f"API返回错误: {response.status_code} {response.text[:200]}",
                )
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _strip_thinking(text: str) -> str:
        import re

        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
