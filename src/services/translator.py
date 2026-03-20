from loguru import logger

from src.exceptions import TranslationError


class Translator:
    def __init__(self):
        pass

    def translate(self, text: str, source_lang: str) -> str | None:
        if source_lang != "en":
            logger.info(f"语言为 {source_lang}，跳过翻译")
            return None

        raise NotImplementedError("翻译功能尚未实现，请配置LLM后端")
