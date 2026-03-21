import shutil
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.config import settings
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
from src.utils.bv import extract_bv_id, get_parts
from src.utils.storage import ResultStorage


class ProcessingPipeline:
    def __init__(self):
        self.downloader = BilibiliDownloader()
        self.stt = SpeechToText()
        self.translator = Translator()
        self.summarizer = Summarizer()
        self.storage = ResultStorage()

    def process(
        self,
        url: str,
        translate: bool = False,
        summarize: bool = False,
        force: bool = False,
    ) -> dict:
        bv_id = extract_bv_id(url)
        video_url = f"https://www.bilibili.com/video/{bv_id}"

        # Get video info
        video_info = self.downloader.get_video_info(url)

        # Get parts info
        parts = get_parts(url)
        total_parts = len(parts)

        # Load existing metadata
        metadata = self.storage.load_metadata(bv_id)
        cached_steps = []

        # Check config changes
        if not force and metadata:
            self._handle_config_changes(bv_id, metadata, total_parts)

        results = []

        for part_info in parts:
            part = part_info.part
            part_result = self._process_part(
                video_url,
                bv_id,
                part,
                total_parts,
                translate,
                summarize,
                force,
                cached_steps,
            )
            results.append(part_result)

        # Update metadata
        self._update_metadata(bv_id, video_url, results, parts, video_info)

        # Build response (return first part result for API compatibility)
        main_result = results[0] if results else {}
        main_result["url"] = video_url
        main_result["result_dir"] = str(self.storage.get_dir(bv_id))
        main_result["cached_steps"] = cached_steps

        if total_parts > 1:
            main_result["parts"] = [
                {
                    "part": r.get("part"),
                    "language": r.get("language"),
                    "transcript": r.get("transcript")[:100] + "...",
                }
                for r in results
            ]

        return main_result

    def _process_part(
        self,
        url: str,
        bv_id: str,
        part: int,
        total_parts: int,
        translate: bool,
        summarize: bool,
        force: bool,
        cached_steps: list,
    ) -> dict:
        result = {"part": part}
        prefix = f"P{part}_" if total_parts > 1 else ""
        audio_path = None

        try:
            # Step 1: Download
            step_name = f"{prefix}download"
            if not force and self.storage.has_audio(bv_id, part, total_parts):
                audio_path = self.storage.get_audio_path(bv_id, part, total_parts)
                cached_steps.append(step_name)
                logger.info(f"缓存命中: {step_name}")
            else:
                logger.info(f"阶段: 下载 - {url} (分P: {part})")
                audio_path = self.downloader.download(url, part)
                audio_path = self.storage.save_audio(
                    bv_id, part, total_parts, audio_path
                )

            # Step 2: STT
            step_name = f"{prefix}stt"
            if not force and self.storage.has_transcript(bv_id, part, total_parts):
                transcript = self.storage.load_transcript(bv_id, part, total_parts)
                cached_steps.append(step_name)
                logger.info(f"缓存命中: {step_name}")
                # Load language and duration from metadata
                metadata = self.storage.load_metadata(bv_id)
                parts_meta = metadata.get("parts", [])
                part_meta = next((p for p in parts_meta if p["part"] == part), {})
                result["language"] = part_meta.get("language", "en")
                result["duration_seconds"] = part_meta.get("duration_seconds")
            else:
                logger.info(f"阶段: 语音识别 (分P: {part})")
                stt_result = self.stt.transcribe(audio_path)
                transcript = stt_result["transcript"]
                result["language"] = stt_result.get("language", "en")
                result["duration_seconds"] = stt_result.get("duration_seconds")
                self.storage.save_transcript(bv_id, part, total_parts, transcript)

            result["transcript"] = transcript

            # Step 3: Translation
            if translate:
                step_name = f"{prefix}translation"
                language = result.get("language", "en")
                if not force and self.storage.has_translation(bv_id, part, total_parts):
                    translation = self.storage.load_translation(
                        bv_id, part, total_parts
                    )
                    cached_steps.append(step_name)
                    logger.info(f"缓存命中: {step_name}")
                else:
                    logger.info(f"阶段: 翻译 (分P: {part})")
                    try:
                        translation = self.translator.translate(transcript, language)
                        if translation:
                            self.storage.save_translation(
                                bv_id, part, total_parts, translation
                            )
                    except TranslationError as e:
                        raise ProcessError("translation", e.code, e.message)
                result["translation"] = translation

            # Step 4: Summarization
            if summarize:
                step_name = f"{prefix}summary"
                if not force and self.storage.has_summary(bv_id, part, total_parts):
                    summary_data = self.storage.load_summary(bv_id, part, total_parts)
                    cached_steps.append(step_name)
                    logger.info(f"缓存命中: {step_name}")
                else:
                    logger.info(f"阶段: 摘要 (分P: {part})")
                    try:
                        summary_data = self.summarizer.summarize(transcript)
                        if summary_data:
                            self.storage.save_summary(
                                bv_id, part, total_parts, summary_data
                            )
                    except SummarizationError as e:
                        raise ProcessError("summarization", e.code, e.message)
                if summary_data and isinstance(summary_data, dict):
                    result["transcript_clean"] = summary_data.get("transcript_clean")
                    result["summary"] = summary_data.get("summary")
                else:
                    result["summary"] = summary_data

            return result

        except DownloadError as e:
            raise ProcessError("download", e.code, e.message)
        except STTError as e:
            raise ProcessError("stt", e.code, e.message)

    def _handle_config_changes(self, bv_id: str, metadata: dict, total_parts: int):
        old_stt = metadata.get("stt_model")
        old_llm = metadata.get("llm_model")

        stt_changed = old_stt and old_stt != settings.qwen_asr_model_path
        llm_changed = old_llm and old_llm != self._get_current_llm_model()

        if not stt_changed and not llm_changed:
            return

        logger.info(f"检测到配置变化: stt={stt_changed}, llm={llm_changed}")

        for part in range(1, total_parts + 1):
            if stt_changed:
                self.storage.rename_old_file(
                    bv_id, part, total_parts, "transcript", old_stt.split("/")[-1]
                )
            if llm_changed:
                self.storage.rename_old_file(
                    bv_id, part, total_parts, "translation", old_llm
                )
                self.storage.rename_old_file(
                    bv_id, part, total_parts, "summary", old_llm
                )

    def _get_current_llm_model(self) -> str:
        return settings.openai_base_url

    def _update_metadata(
        self,
        bv_id: str,
        url: str,
        results: list,
        parts: list,
        video_info: dict | None = None,
    ):
        metadata = self.storage.load_metadata(bv_id)
        metadata.update(
            {
                "url": url,
                "bv_id": bv_id,
                "video": video_info or {},
                "stt_model": settings.qwen_asr_model_path,
                "llm_model": self._get_current_llm_model(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if "created_at" not in metadata:
            metadata["created_at"] = metadata["updated_at"]

        # Update parts info
        parts_meta = metadata.get("parts", [])
        for i, result in enumerate(results):
            part_num = result.get("part", i + 1)
            part_entry = next((p for p in parts_meta if p["part"] == part_num), None)
            if not part_entry:
                part_entry = {"part": part_num}
                parts_meta.append(part_entry)

            total_parts = len(parts)
            update_dict = {
                "has_audio": self.storage.has_audio(bv_id, part_num, total_parts),
                "has_transcript": self.storage.has_transcript(
                    bv_id, part_num, total_parts
                ),
                "has_translation": self.storage.has_translation(
                    bv_id, part_num, total_parts
                ),
                "has_summary": self.storage.has_summary(bv_id, part_num, total_parts),
            }
            # Only update language/duration if result has them (not cached)
            if result.get("language") is not None:
                update_dict["language"] = result.get("language")
            if result.get("duration_seconds") is not None:
                update_dict["duration_seconds"] = result.get("duration_seconds")
            part_entry.update(update_dict)

        metadata["parts"] = sorted(parts_meta, key=lambda p: p["part"])
        self.storage.save_metadata(bv_id, metadata)
