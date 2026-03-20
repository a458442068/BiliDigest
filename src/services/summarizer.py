from loguru import logger

from src.exceptions import SummarizationError


class Summarizer:
    def __init__(self):
        pass

    def summarize(self, text: str) -> str | None:
        raise NotImplementedError("摘要功能尚未实现，请配置LLM后端")
