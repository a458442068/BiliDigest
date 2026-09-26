import json
import re

import httpx
from loguru import logger

from src.config import settings
from src.exceptions import SummarizationError


class Summarizer:
    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY 未配置，摘要功能将不可用")

    async def summarize(self, text: str, template: str = "general") -> dict | None:
        if not text or len(text.strip()) < 10:
            logger.warning("文本内容过短，跳过摘要")
            return None

        if not settings.openai_api_key:
            raise SummarizationError("LLM_API_ERROR", "OPENAI_API_KEY 未配置")

        logger.info("调用LLM API生成摘要")
        try:
            result = await self._call_llm(text, template)
            result = self._normalise_result(result)
            logger.info("摘要生成完成")
            return result
        except SummarizationError:
            raise
        except Exception as e:
            raise SummarizationError("LLM_API_ERROR", f"摘要API调用失败: {e}")

    async def _call_llm(self, text: str, template: str) -> dict:
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
                        "你是一个专业的中文内容整理助手。请分析下面的文字稿，并且只返回一个合法 JSON 对象，不要使用 Markdown 代码块。\n\n"
                        "JSON 必须包含这些字段：transcript_clean（整理后的完整文字稿，字符串）、summary（简洁摘要，字符串）、"
                        "key_points（主要观点字符串数组）、chapters（章节数组，每项包含 title 和 summary 字符串，可选 start_seconds 数字）、"
                        "action_items（行动项字符串数组）、entities（实体数组，每项包含 name 和 type 字符串）。\n\n"
                        "所有内容使用中文，专有名词保留原文。整理文字稿时只删除口头语、重复和明显口误，不改变事实和观点。"
                        f"摘要模板为 {template}：{self._template_instruction(template)}\n\n"
                        "如果没有行动项、章节或实体，返回空数组。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=600) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise SummarizationError(
                    "LLM_API_ERROR",
                    f"API返回错误: {response.status_code} {response.text[:200]}",
                )
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_response(content)

    @staticmethod
    def _template_instruction(template: str) -> str:
        return {
            "general": "突出主题、结论和关键事实",
            "notes": "按知识点组织，适合复习和后续检索",
            "meeting": "突出参与者观点、决定和待办事项",
            "study": "突出概念、例子、难点和复习问题",
        }.get(template, "突出主题、结论和关键事实")

    @staticmethod
    def _parse_response(content: str) -> dict:
        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Backward-compatible parsing for older local model prompts.
        parts = cleaned.split("---SUMMARY---")
        if len(parts) >= 2:
            transcript_part = parts[0].replace("---TRANSCRIPT_CLEAN---", "").strip()
            return {
                "transcript_clean": transcript_part,
                "summary": parts[1].strip(),
                "key_points": [],
                "chapters": [],
                "action_items": [],
                "entities": [],
            }
        raise ValueError("LLM 返回的摘要不是合法 JSON")

    @classmethod
    def _normalise_result(cls, result: dict) -> dict:
        transcript_clean = result.get("transcript_clean")
        summary = result.get("summary")
        if not isinstance(transcript_clean, str) or not isinstance(summary, str):
            raise ValueError("LLM 摘要缺少 transcript_clean 或 summary 字段")
        return {
            "transcript_clean": cls._strip_thinking(transcript_clean),
            "summary": cls._strip_thinking(summary),
            "key_points": cls._string_list(result.get("key_points")),
            "chapters": cls._chapter_list(result.get("chapters")),
            "action_items": cls._string_list(result.get("action_items")),
            "entities": cls._entity_list(result.get("entities")),
        }

    @staticmethod
    def _string_list(value) -> list[str]:
        return [str(item).strip() for item in (value or []) if str(item).strip()]

    @staticmethod
    def _chapter_list(value) -> list[dict]:
        chapters = []
        for item in value or []:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            chapter = {
                "title": str(item["title"]).strip(),
                "summary": str(item.get("summary", "")).strip(),
            }
            if item.get("start_seconds") is not None:
                try:
                    chapter["start_seconds"] = float(item["start_seconds"])
                except (TypeError, ValueError):
                    pass
            chapters.append(chapter)
        return chapters

    @staticmethod
    def _entity_list(value) -> list[dict]:
        entities = []
        for item in value or []:
            if isinstance(item, dict) and item.get("name"):
                entities.append(
                    {"name": str(item["name"]).strip(), "type": str(item.get("type", "其他")).strip()}
                )
        return entities

    @staticmethod
    def _strip_thinking(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
