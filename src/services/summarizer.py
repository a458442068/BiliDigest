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
            result = self._normalise_result(result, text)
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
                        "你是中文内容整理助手。请完整分析下面的文字稿，只输出以下六个分隔段，"
                        "不要输出 JSON、Markdown 代码块或额外解释。每个分隔标记必须单独占一行，"
                        "标记名称和横线必须完全保持不变。\n\n"
                        "---TRANSCRIPT_CLEAN---\n"
                        "输出整理后的完整文字稿：只删除语气词、重复和明显口误，不删减事实、观点、例子或重要细节。\n\n"
                        "---SUMMARY---\n"
                        "输出详细摘要，覆盖主题、背景、主要论点、关键事实、结论和限制；分成 3 到 8 段。\n\n"
                        "---KEY_POINTS---\n"
                        "每行一个关键观点，以 - 开头；没有则写 - 无。\n\n"
                        "---CHAPTERS---\n"
                        "每行一个章节，格式为“章节标题 | 章节摘要”；没有则写 - 无。\n\n"
                        "---ACTION_ITEMS---\n"
                        "只列出原文明确提到的待办或建议，每行一个，以 - 开头；没有则写 - 无。\n\n"
                        "---ENTITIES---\n"
                        "每行一个实体，格式为“名称 | 类型”；没有则写 - 无。\n\n"
                        "所有内容使用中文，专有名词保留原文。"
                        f"摘要模板为 {template}：{self._template_instruction(template)}。"
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
        cleaned = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        sections = Summarizer._parse_marked_sections(cleaned)
        if sections:
            return sections

        if cleaned:
            logger.warning("LLM 未返回结构化摘要，已降级为纯文本结果")
            return {
                "summary": cleaned,
                "key_points": [],
                "action_items": [],
            }
        raise ValueError("LLM 返回为空")

    @staticmethod
    def _parse_marked_sections(content: str) -> dict | None:
        names = (
            "TRANSCRIPT_CLEAN",
            "SUMMARY",
            "KEY_POINTS",
            "CHAPTERS",
            "ACTION_ITEMS",
            "ENTITIES",
        )
        pattern = re.compile(r"(?m)^---(" + "|".join(names) + r")---\s*$")
        matches = list(pattern.finditer(content))
        if not matches:
            return None
        result = {
            "key_points": [],
            "chapters": [],
            "action_items": [],
            "entities": [],
        }
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            value = content[match.end():end].strip()
            name = match.group(1)
            if name == "TRANSCRIPT_CLEAN" or name == "SUMMARY":
                result["transcript_clean" if name == "TRANSCRIPT_CLEAN" else "summary"] = value
            elif name in {"KEY_POINTS", "ACTION_ITEMS"}:
                result["key_points" if name == "KEY_POINTS" else "action_items"] = [
                    line.lstrip("-•* ").strip()
                    for line in value.splitlines()
                    if line.strip() and line.strip() not in {"无", "- 无"}
                ]
            elif name == "CHAPTERS":
                result["chapters"] = Summarizer._parse_pair_lines(value)
            elif name == "ENTITIES":
                result["entities"] = [
                    {"name": pair[0], "type": pair[1] or "其他"}
                    for pair in Summarizer._parse_pairs(value)
                ]
        return result if result.get("summary") else None

    @staticmethod
    def _parse_pairs(value: str) -> list[tuple[str, str]]:
        pairs = []
        for line in value.splitlines():
            line = line.lstrip("-•* ").strip()
            if not line or line in {"无", "- 无"}:
                continue
            parts = [part.strip() for part in line.split("|", 1)]
            pairs.append((parts[0], parts[1] if len(parts) == 2 else ""))
        return pairs

    @staticmethod
    def _parse_pair_lines(value: str) -> list[dict]:
        return [
            {"title": title, "summary": summary}
            for title, summary in Summarizer._parse_pairs(value)
        ]

    @classmethod
    def _normalise_result(cls, result: dict, source_text: str = "") -> dict:
        transcript_clean = result.get("transcript_clean") or source_text
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
