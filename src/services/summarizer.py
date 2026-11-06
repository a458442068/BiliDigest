import json
import re
from ast import literal_eval

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
                        "你是一个专业的中文内容整理助手。请分析下面的文字稿。为降低格式错误，禁止输出 JSON、Markdown 代码块或额外解释，严格按以下标题输出六段文本；每个标题必须独占一行：\n\n"
                        "[整理稿]\n整理后的完整文字稿\n[摘要]\n简洁摘要\n[关键观点]\n每行一个观点，以 - 开头；没有则写 - 无\n"
                        "[章节]\n每行一个章节标题；没有则写 - 无\n[行动项]\n每行一个行动项，以 - 开头；没有则写 - 无\n[实体]\n每行一个实体名称；没有则写 - 无\n\n"
                        "所有内容使用中文，专有名词保留原文。整理文字稿时只删除口头语、重复和明显口误，不改变事实和观点。"
                        f"摘要模板为 {template}：{self._template_instruction(template)}\n\n"
                        "如果没有行动项、章节或实体，只写 - 无。"
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
            return self._parse_response(content, source_text=text)

    @staticmethod
    def _template_instruction(template: str) -> str:
        return {
            "general": "突出主题、结论和关键事实",
            "notes": "按知识点组织，适合复习和后续检索",
            "meeting": "突出参与者观点、决定和待办事项",
            "study": "突出概念、例子、难点和复习问题",
        }.get(template, "突出主题、结论和关键事实")

    @staticmethod
    def _parse_response(content: str, source_text: str | None = None) -> dict:
        cleaned = Summarizer._clean_model_output(content)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Some local models emit a Python-style dict (single quotes/trailing commas).
        try:
            parsed = literal_eval(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except (SyntaxError, ValueError):
            pass

        # Accept prose surrounding a JSON object, which is common with instruct models.
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", cleaned):
            try:
                parsed, _ = decoder.raw_decode(cleaned[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        section_result = Summarizer._parse_sections(cleaned)
        if section_result:
            return section_result

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

        # Last-resort fallback: preserve the source transcript and expose the model
        # response as a plain summary. This keeps small local models usable even when
        # they ignore every formatting instruction.
        if cleaned:
            logger.warning("LLM 未返回结构化摘要，已降级为纯文本结果")
            return {
                "transcript_clean": source_text or cleaned,
                "summary": cleaned,
                "key_points": [],
                "chapters": [],
                "action_items": [],
                "entities": [],
            }
        raise ValueError("LLM 返回为空")

    @staticmethod
    def _clean_model_output(content: str) -> str:
        cleaned = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
        return re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()

    @staticmethod
    def _parse_sections(content: str) -> dict | None:
        """Parse a compact marker format that is easier for small models than JSON."""
        aliases = {
            "transcript_clean": r"整理稿|整理版文字稿|TRANSCRIPT_CLEAN",
            "summary": r"摘要|SUMMARY",
            "key_points": r"关键观点|主要观点|KEY_POINTS",
            "chapters": r"章节|CHAPTERS",
            "action_items": r"行动项|待办事项|ACTION_ITEMS",
            "entities": r"实体|ENTITIES",
        }
        positions = []
        for key, alias in aliases.items():
            match = re.search(rf"(?im)^\s*(?:\[\s*)?(?:{alias})(?:\s*\])?\s*[:：]?\s*$", content)
            if match:
                positions.append((match.start(), match.end(), key))
        if not positions:
            return None
        positions.sort()
        result = {"key_points": [], "chapters": [], "action_items": [], "entities": []}
        for index, (_, end, key) in enumerate(positions):
            next_start = positions[index + 1][0] if index + 1 < len(positions) else len(content)
            value = content[end:next_start].strip()
            if key in {"transcript_clean", "summary"}:
                result[key] = value
            elif key == "key_points" or key == "action_items":
                result[key] = [line.lstrip("-•* ").strip() for line in value.splitlines() if line.strip()]
            elif key == "chapters":
                result[key] = [
                    {"title": line.lstrip("-•* ").strip(), "summary": ""}
                    for line in value.splitlines() if line.strip()
                ]
            elif key == "entities":
                result[key] = [
                    {"name": line.lstrip("-•* ").strip(), "type": "其他"}
                    for line in value.splitlines() if line.strip()
                ]
        return result if result.get("summary") or result.get("transcript_clean") else None

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
        if isinstance(value, str):
            value = value.splitlines()
        return [
            item.strip()
            for item in (str(item).lstrip("-•* ").strip() for item in (value or []))
            if item and item not in {"无", "无。", "none", "None"}
        ]

    @staticmethod
    def _chapter_list(value) -> list[dict]:
        chapters = []
        for item in value or []:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            if str(item["title"]).strip() in {"无", "无。", "none", "None"}:
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
                if str(item["name"]).strip() in {"无", "无。", "none", "None"}:
                    continue
                entities.append(
                    {"name": str(item["name"]).strip(), "type": str(item.get("type", "其他")).strip()}
                )
        return entities

    @staticmethod
    def _strip_thinking(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
