import httpx
from loguru import logger

from src.config import settings
from src.exceptions import SummarizationError


class Summarizer:
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，摘要功能将不可用")

    def summarize(self, text: str) -> dict | None:
        if not text or len(text.strip()) < 10:
            logger.warning("文本内容过短，跳过摘要")
            return None

        if not settings.openai_api_key:
            raise SummarizationError("LLM_API_ERROR", "OPENAI_API_KEY 未配置")

        logger.info("调用LLM API生成摘要")
        try:
            result = self._call_llm(text)
            result["transcript_clean"] = self._strip_thinking(
                result["transcript_clean"]
            )
            result["summary"] = self._strip_thinking(result["summary"])
            logger.info("摘要生成完成")
            return result
        except SummarizationError:
            raise
        except Exception as e:
            raise SummarizationError("LLM_API_ERROR", f"摘要API调用失败: {e}")

    def _call_llm(self, text: str) -> dict:
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
                        "你是一个专业的文本处理助手。请对以下文字稿生成两份内容，用 `---TRANSCRIPT_CLEAN---` 和 `---SUMMARY---` 分隔。\n\n"
                        "1. 【整理版文字稿】在 `---TRANSCRIPT_CLEAN---` 之后：保留原文完整内容和原意，仅去除口语中的语气词、重复、口误等冗余，使语句通顺流畅。不要改变任何观点或信息。\n\n"
                        "2. 【内容摘要】在 `---SUMMARY---` 之后：涵盖原文的主要观点、关键信息和核心结论，语言简洁精炼，适合快速了解全文内容。\n\n"
                        "请严格按照格式输出，不要添加其他说明。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        with httpx.Client(timeout=600) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise SummarizationError(
                    "LLM_API_ERROR",
                    f"API返回错误: {response.status_code} {response.text[:200]}",
                )
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_response(content)

    @staticmethod
    def _parse_response(content: str) -> dict:
        parts = content.split("---SUMMARY---")
        if len(parts) >= 2:
            transcript_part = parts[0].replace("---TRANSCRIPT_CLEAN---", "").strip()
            summary_part = parts[1].strip()
            return {"transcript_clean": transcript_part, "summary": summary_part}
        return {"transcript_clean": content, "summary": content}

    @staticmethod
    def _strip_thinking(text: str) -> str:
        import re

        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
