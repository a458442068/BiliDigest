import os
from pathlib import Path

from loguru import logger

from src.exceptions import (
    DownloadError,
    STTError,
    TranslationError,
    SummarizationError,
    ProcessError,
)
from src.services.downloader import BilibiliDownloader
from src.services.stt import SpeechToText
from src.services.translator import Translator
from src.services.summarizer import Summarizer


class ProcessingPipeline:
    def __init__(self):
        self.downloader = BilibiliDownloader()
        self.stt = SpeechToText()
        self.translator = Translator()
        self.summarizer = Summarizer()

    def process(
        self, url: str, translate: bool = False, summarize: bool = False
    ) -> dict:
        result = {}
        audio_path = None

        try:
            # Step 1: Download
            logger.info(f"阶段: 下载 - {url}")
            audio_path = self.downloader.download(url)

            # Step 2: STT
            logger.info("阶段: 语音识别")
            stt_result = self.stt.transcribe(audio_path)
            result.update(stt_result)

            # Step 3: Translation
            if translate:
                logger.info("阶段: 翻译")
                try:
                    translation = self.translator.translate(
                        stt_result["transcript"], stt_result.get("language", "en")
                    )
                    result["translation"] = translation
                except TranslationError as e:
                    raise ProcessError("translation", e.code, e.message)

            # Step 4: Summarization
            if summarize:
                logger.info("阶段: 摘要")
                try:
                    summary = self.summarizer.summarize(stt_result["transcript"])
                    result["summary"] = summary
                except SummarizationError as e:
                    raise ProcessError("summarization", e.code, e.message)

            result["url"] = url
            return result

        except DownloadError as e:
            raise ProcessError("download", e.code, e.message)
        except STTError as e:
            raise ProcessError("stt", e.code, e.message)
        finally:
            self._cleanup(audio_path)

    def _cleanup(self, audio_path: str | None):
        if audio_path:
            try:
                p = Path(audio_path)
                if p.exists():
                    p.unlink()
                    logger.info(f"已清理临时文件: {audio_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
