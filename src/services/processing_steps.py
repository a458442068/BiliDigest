from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from loguru import logger

from src.exceptions import ProcessError, SummarizationError, TranslationError
from src.models.domain import ProcessingStep, StepResult


@dataclass
class StepContext:
    url: str
    bv_id: str
    part: int
    total_parts: int
    force: bool
    storage: Any
    downloader: Any
    stt: Any
    translator: Any
    summarizer: Any
    summary_template: str
    run_io: Callable[..., Awaitable[Any]]
    run_stt: Callable[..., Awaitable[Any]]

    @property
    def prefix(self) -> str:
        return f"P{self.part}_" if self.total_parts > 1 else ""


class DownloadStep:
    step = ProcessingStep.DOWNLOAD
    progress_step = "downloading"

    async def run(self, context: StepContext, result: dict) -> StepResult:
        cache_name = f"{context.prefix}download"
        if not context.force and context.storage.has_audio(
            context.bv_id, context.part, context.total_parts
        ):
            audio_path = context.storage.get_audio_path(
                context.bv_id, context.part, context.total_parts
            )
            logger.info(f"缓存命中: {cache_name}")
            return StepResult(
                step=self.step,
                part=context.part,
                cached=True,
                data={"audio_path": audio_path},
            )

        logger.info(f"阶段: 下载 - {context.url} (分P: {context.part})")
        with context.storage.audio_download_transaction(
            context.bv_id, context.part, context.total_parts
        ) as tx:
            downloaded_path = await context.run_io(
                context.downloader.download,
                context.url,
                context.part,
                str(tx.work_dir),
            )
            audio_path = await context.run_io(tx.commit_audio, downloaded_path)
        return StepResult(
            step=self.step,
            part=context.part,
            cached=False,
            data={"audio_path": audio_path},
        )


class TranscribeStep:
    step = ProcessingStep.STT
    progress_step = "stt"

    async def run(self, context: StepContext, result: dict) -> StepResult:
        cache_name = f"{context.prefix}stt"
        if not context.force and context.storage.has_transcript(
            context.bv_id, context.part, context.total_parts
        ):
            transcript = await context.run_io(
                context.storage.load_transcript,
                context.bv_id,
                context.part,
                context.total_parts,
            )
            metadata = await context.run_io(context.storage.load_metadata, context.bv_id)
            parts_meta = metadata.get("parts", [])
            part_meta = next(
                (p for p in parts_meta if p.get("part") == context.part), {}
            )
            logger.info(f"缓存命中: {cache_name}")
            return StepResult(
                step=self.step,
                part=context.part,
                cached=True,
                data={
                    "transcript": transcript,
                    "language": part_meta.get("language", "en"),
                    "duration_seconds": part_meta.get("duration_seconds"),
                },
            )

        logger.info(f"阶段: 语音识别 (分P: {context.part})")
        if not result.get("audio_path"):
            raise ProcessError("download", "MISSING_AUDIO", "缺少音频，无法从STT开始")
        stt_result = await context.run_stt(
            context.stt.transcribe, result.get("audio_path")
        )
        transcript = stt_result["transcript"]
        data = {
            "transcript": transcript,
            "language": stt_result.get("language", "en"),
            "duration_seconds": stt_result.get("duration_seconds"),
        }
        await context.run_io(
            context.storage.save_transcript,
            context.bv_id,
            context.part,
            context.total_parts,
            transcript,
        )
        segments = stt_result.get("segments")
        if segments:
            await context.run_io(
                context.storage.save_segments,
                context.bv_id,
                context.part,
                context.total_parts,
                segments,
            )
        return StepResult(
            step=self.step, part=context.part, cached=False, data=data
        )


class TranslateStep:
    step = ProcessingStep.TRANSLATION
    progress_step = "translating"

    async def run(self, context: StepContext, result: dict) -> StepResult:
        cache_name = f"{context.prefix}translation"
        if not context.force and context.storage.has_translation(
            context.bv_id, context.part, context.total_parts
        ):
            translation = await context.run_io(
                context.storage.load_translation,
                context.bv_id,
                context.part,
                context.total_parts,
            )
            logger.info(f"缓存命中: {cache_name}")
            return StepResult(
                step=self.step,
                part=context.part,
                cached=True,
                data={"translation": translation},
            )

        logger.info(f"阶段: 翻译 (分P: {context.part})")
        try:
            transcript = result.get("transcript")
            if transcript is None:
                transcript = await context.run_io(
                    context.storage.load_transcript,
                    context.bv_id,
                    context.part,
                    context.total_parts,
                )
            translation = await context.translator.translate(
                transcript, result.get("language", "en")
            )
            if translation:
                await context.run_io(
                    context.storage.save_translation,
                    context.bv_id,
                    context.part,
                    context.total_parts,
                    translation,
                )
        except TranslationError as e:
            raise ProcessError("translation", e.code, e.message) from e

        return StepResult(
            step=self.step,
            part=context.part,
            cached=False,
            data={"translation": translation},
        )


class SummarizeStep:
    step = ProcessingStep.SUMMARY
    progress_step = "summarizing"

    async def run(self, context: StepContext, result: dict) -> StepResult:
        cache_name = f"{context.prefix}summary"
        cached = False
        if not context.force and context.storage.has_summary(
            context.bv_id, context.part, context.total_parts
        ):
            insights = await context.run_io(
                context.storage.load_insights,
                context.bv_id,
                context.part,
                context.total_parts,
            )
            cached = insights.get("summary_template") == context.summary_template
        if cached:
            summary_data = await context.run_io(
                context.storage.load_summary,
                context.bv_id,
                context.part,
                context.total_parts,
            )
            logger.info(f"缓存命中: {cache_name}")
        else:
            logger.info(f"阶段: 摘要 (分P: {context.part})")
            try:
                summary_input = result.get("translation")
                if summary_input is None and context.storage.has_translation(
                    context.bv_id, context.part, context.total_parts
                ):
                    summary_input = await context.run_io(
                        context.storage.load_translation,
                        context.bv_id,
                        context.part,
                        context.total_parts,
                    )
                if summary_input is None:
                    summary_input = result.get("transcript")
                if summary_input is None:
                    summary_input = await context.run_io(
                        context.storage.load_transcript,
                        context.bv_id,
                        context.part,
                        context.total_parts,
                    )
                try:
                    summary_data = await context.summarizer.summarize(
                        summary_input, template=context.summary_template
                    )
                except TypeError as exc:
                    # Keep compatibility with lightweight custom summarizers used locally.
                    if "template" not in str(exc):
                        raise
                    summary_data = await context.summarizer.summarize(summary_input)
                if summary_data:
                    if isinstance(summary_data, dict):
                        summary_data = {
                            **summary_data,
                            "summary_template": context.summary_template,
                        }
                    await context.run_io(
                        context.storage.save_summary,
                        context.bv_id,
                        context.part,
                        context.total_parts,
                        summary_data,
                    )
            except SummarizationError as e:
                raise ProcessError("summarization", e.code, e.message) from e

        data = {}
        if summary_data and isinstance(summary_data, dict):
            data["transcript_clean"] = summary_data.get("transcript_clean")
            data["summary"] = summary_data.get("summary")
            data["key_points"] = summary_data.get("key_points", [])
            data["chapters"] = summary_data.get("chapters", [])
            data["action_items"] = summary_data.get("action_items", [])
            data["entities"] = summary_data.get("entities", [])
            data["summary_template"] = context.summary_template
        else:
            data["summary"] = summary_data
        return StepResult(
            step=self.step,
            part=context.part,
            cached=cached,
            data=data,
        )
