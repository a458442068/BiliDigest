import os
from pathlib import Path

from loguru import logger

from src.exceptions import DownloadError, STTError, ProcessError
from src.services.downloader import BilibiliDownloader
from src.services.stt import SpeechToText


class ProcessingPipeline:
    def __init__(self):
        self.downloader = BilibiliDownloader()
        self.stt = SpeechToText()

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

            # Step 3: Translation (placeholder)
            if translate and stt_result.get("language") == "en":
                logger.info("阶段: 翻译 (占位)")
                result["translation"] = None

            # Step 4: Summarization (placeholder)
            if summarize:
                logger.info("阶段: 摘要 (占位)")
                result["summary"] = None

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
