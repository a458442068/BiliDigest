import httpx
from loguru import logger

from src.config import settings
from src.exceptions import TranslationError


class Translator:
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，翻译功能将不可用")

    def translate(self, text: str, source_lang: str) -> str | None:
        lang = source_lang.lower().strip()
        if lang not in ("en", "english"):
            logger.info(f"语言为 {source_lang}，跳过翻译")
            return None

        if not settings.openai_api_key:
            raise TranslationError("LLM_API_ERROR", "OPENAI_API_KEY 未配置")

        logger.info("调用LLM API进行翻译")
        try:
            translated = self._call_llm(text)
            translated = self._strip_thinking(translated)
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
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的翻译助手。请将以下内容翻译为中文。"
                        "核心要求：忠实原文，尽量保持原意和语气，不增删内容，不进行意译或改写。"
                        "专有名词保留原文或提供通用译名。只返回翻译结果，不要添加任何解释。"
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
