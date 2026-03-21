import httpx
from loguru import logger

from src.config import settings
from src.exceptions import TranslationError


class Translator:
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，翻译功能将不可用")

    def translate(self, text: str, source_lang: str) -> str | None:
        if not settings.openai_api_key:
            raise TranslationError("LLM_API_ERROR", "OPENAI_API_KEY 未配置")

        logger.info(f"调用LLM API进行翻译 (source_lang={source_lang})")
        try:
            translated = self._call_llm(text)
            translated = self._strip_thinking(translated)
            if translated.strip() == text.strip():
                logger.info("LLM判断为中文，无需翻译")
                return None
            logger.info("翻译完成")
            return translated
        except TranslationError:
            raise
        except Exception as e:
            raise TranslationError("LLM_API_ERROR", f"翻译API调用失败: {e}")

    def _call_llm(self, text: str) -> str:
        url = f"{settings.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "将以下文本翻译成中文。如果文本已经是中文，直接返回原文。"
                        "忠实原文，专有名词保留原文。只输出翻译结果。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        with httpx.Client(timeout=600) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise TranslationError(
                    "LLM_API_ERROR",
                    f"API返回错误: {response.status_code} {response.text[:200]}",
                )
            data = response.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _strip_thinking(text: str) -> str:
        import re

        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
