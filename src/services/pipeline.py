import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from loguru import logger

from src.config import settings
from src.exceptions import (
    DownloadError,
    STTError,
    ProcessError,
)
from src.services.downloader import BilibiliDownloader
from src.services.stt import SpeechToText
from src.services.translator import Translator
from src.services.summarizer import Summarizer
from src.models.domain import ArtifactKind, ProcessingRequest, ProcessingStep, VideoRef
from src.models.schemas import ProgressInfo
from src.services.processing_steps import (
    DownloadStep,
    StepContext,
    SummarizeStep,
    TranscribeStep,
    TranslateStep,
)
from src.utils.bv import get_parts, get_source_name
from src.utils.storage import ResultStorage

# STT 专用线程池：max_workers=1 保证 GPU 串行，避免显存争抢
_stt_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stt")


def _to_thread(func, *args):
    """将同步函数放到默认线程池执行，不阻塞事件循环。"""
    return asyncio.get_event_loop().run_in_executor(None, func, *args)


def _to_stt(func, *args):
    """将 STT 函数放到专用线程池执行，GPU 串行。"""
    return asyncio.get_event_loop().run_in_executor(_stt_executor, func, *args)


class ProcessingPipeline:
    def __init__(self):
        self.downloader = BilibiliDownloader()
        self.stt = SpeechToText()
        self.translator = Translator()
        self.summarizer = Summarizer()
        self.storage = ResultStorage()
        self.steps = {
            ProcessingStep.DOWNLOAD: DownloadStep(),
            ProcessingStep.STT: TranscribeStep(),
            ProcessingStep.TRANSLATION: TranslateStep(),
            ProcessingStep.SUMMARY: SummarizeStep(),
        }
        self._progress: dict[str, ProgressInfo] = {}

    def get_progress(self, bv_id: str) -> ProgressInfo | None:
        if bv_id in self._progress:
            return self._progress[bv_id]
        try:
            metadata = self.storage.load_metadata(bv_id)
        except ValueError:
            return None
        if not metadata:
            return None
        return self._progress_from_metadata(bv_id, metadata)

    def clear_progress(self, bv_id: str):
        self._progress.pop(bv_id, None)

    def mark_queued(self, bv_id: str, total_parts: int = 1):
        self._progress[bv_id] = ProgressInfo(
            bv_id=bv_id,
            status="queued",
            current_step="queued",
            step_progress=0.0,
            total_parts=total_parts,
            current_part=1,
        )
        self._persist_progress(bv_id)

    def _set_progress(self, bv_id: str, **kwargs):
        if bv_id in self._progress:
            info = self._progress[bv_id]
            for k, v in kwargs.items():
                setattr(info, k, v)
            self._persist_progress(bv_id)

    def _progress_from_metadata(self, bv_id: str, metadata: dict) -> ProgressInfo:
        status = metadata.get("status") or "done"
        total_parts = metadata.get("total_parts") or len(metadata.get("parts", [])) or 1
        current_step = metadata.get("current_step") or (
            "done" if status == "done" else "queued"
        )
        step_progress = metadata.get("step_progress")
        if step_progress is None:
            step_progress = 1.0 if status == "done" else 0.0
        return ProgressInfo(
            bv_id=bv_id,
            status=status,
            current_step=current_step,
            step_progress=step_progress,
            total_parts=total_parts,
            current_part=metadata.get("current_part") or 1,
            error=metadata.get("error"),
        )

    def _persist_progress(self, bv_id: str):
        info = self._progress.get(bv_id)
        if not info:
            return
        metadata = self.storage.load_metadata(bv_id)
        metadata.update(
            {
                "bv_id": bv_id,
                "status": info.status,
                "current_step": info.current_step,
                "step_progress": info.step_progress,
                "total_parts": info.total_parts,
                "current_part": info.current_part,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if info.error:
            metadata["error"] = info.error
        else:
            metadata.pop("error", None)
        if "created_at" not in metadata:
            metadata["created_at"] = metadata["updated_at"]
        self.storage.save_metadata(bv_id, metadata)

    async def process(
        self,
        url: str,
        translate: bool = False,
        summarize: bool = False,
        force: bool = False,
        target_parts: set[int] | None = None,
        from_step: str | None = None,
    ) -> dict:
        return await self.process_request(
            ProcessingRequest(
                url=url,
                translate=translate,
                summarize=summarize,
                force=force,
                target_parts=target_parts,
                from_step=from_step,
            )
        )

    async def process_request(self, request: ProcessingRequest) -> dict:
        video_ref = VideoRef.from_input(request.url)
        bv_id = video_ref.bv_id
        video_url = video_ref.url
        self.mark_queued(bv_id)

        try:
            # Get video info
            video_info = await _to_thread(self.downloader.get_video_info, request.url)

            # Get parts info
            parts = await _to_thread(get_parts, request.url)
            total_parts = len(parts)
            part_numbers = {part.part for part in parts}
            selected_parts = parts
            if request.target_parts is not None:
                invalid_parts = sorted(request.target_parts - part_numbers)
                if invalid_parts:
                    raise ProcessError(
                        "process",
                        "INVALID_PART",
                        f"分P不存在: {', '.join(str(p) for p in invalid_parts)}",
                    )
                if not request.target_parts:
                    raise ProcessError("process", "INVALID_PART", "未选择分P")
                selected_parts = [
                    part for part in parts if part.part in request.target_parts
                ]

            self._set_progress(
                bv_id,
                status="processing",
                current_step="downloading",
                step_progress=0.0,
                total_parts=total_parts,
            )

            return await self._process_inner(
                bv_id,
                video_url,
                request.url,
                parts,
                selected_parts,
                total_parts,
                request.translate,
                request.summarize,
                request.force,
                request.from_step,
                video_info,
            )
        except Exception as e:
            error_message = getattr(e, "message", str(e)) or "处理失败"
            error_step = getattr(e, "stage", "unknown")
            self._set_progress(
                bv_id,
                status="error",
                current_step=error_step,
                step_progress=0.0,
                error=error_message,
            )
            raise
        finally:
            if bv_id in self._progress and self._progress[bv_id].status in (
                "queued",
                "processing",
            ):
                self._set_progress(
                    bv_id, status="done", current_step="done", step_progress=1.0
                )
            if bv_id in self._progress and self._progress[bv_id].status in (
                "done",
                "error",
            ):
                self.clear_progress(bv_id)

    async def _process_inner(
        self,
        bv_id: str,
        video_url: str,
        url: str,
        parts: list,
        selected_parts: list,
        total_parts: int,
        translate: bool,
        summarize: bool,
        force: bool,
        from_step: ProcessingStep | None,
        video_info: dict,
    ) -> dict:
        # Load existing metadata
        metadata = await _to_thread(self.storage.load_metadata, bv_id)
        cached_steps = []

        # Check config changes
        if not force and metadata:
            self._handle_config_changes(
                bv_id,
                metadata,
                total_parts,
                [part.part for part in selected_parts],
            )

        # 写入初始 metadata（has_* 全为 false，admin 页面可见处理中状态）
        await _to_thread(self._update_metadata, bv_id, video_url, [], parts, video_info)

        results = []
        steps = self._steps_for_request(translate, summarize, from_step)

        for part_info in selected_parts:
            part = part_info.part
            self._set_progress(bv_id, current_part=part)
            part_result = await self._process_part(
                video_url,
                bv_id,
                part,
                total_parts,
                force,
                steps,
                cached_steps,
                video_info,
                parts,
            )
            results.append(part_result)

        # Update metadata
        await _to_thread(
            self._update_metadata,
            bv_id,
            video_url,
            results,
            parts,
            video_info,
        )

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
                    "transcript": (r.get("transcript") or "")[:100] + "...",
                }
                for r in results
            ]

        return main_result

    def _steps_for_request(
        self,
        translate: bool,
        summarize: bool,
        from_step: ProcessingStep | None,
    ) -> list[ProcessingStep]:
        steps = [ProcessingStep.DOWNLOAD, ProcessingStep.STT]
        if translate:
            steps.append(ProcessingStep.TRANSLATION)
        if summarize:
            steps.append(ProcessingStep.SUMMARY)
        if from_step is None:
            return steps
        ordered_steps = [
            ProcessingStep.DOWNLOAD,
            ProcessingStep.STT,
            ProcessingStep.TRANSLATION,
            ProcessingStep.SUMMARY,
        ]
        start_index = ordered_steps.index(from_step)
        selected_steps = [
            step for step in steps if ordered_steps.index(step) >= start_index
        ]
        if not selected_steps:
            raise ProcessError(
                "process",
                "INVALID_STEP",
                f"当前处理选项不会执行步骤: {from_step.value}",
            )
        return selected_steps

    async def _process_part(
        self,
        url: str,
        bv_id: str,
        part: int,
        total_parts: int,
        force: bool,
        steps: list[ProcessingStep],
        cached_steps: list,
        video_info: dict,
        parts: list,
    ) -> dict:
        result = {"part": part}
        context = StepContext(
            url=url,
            bv_id=bv_id,
            part=part,
            total_parts=total_parts,
            force=force or steps[0] != ProcessingStep.DOWNLOAD,
            storage=self.storage,
            downloader=self.downloader,
            stt=self.stt,
            translator=self.translator,
            summarizer=self.summarizer,
            run_io=_to_thread,
            run_stt=_to_stt,
        )
        if ProcessingStep.DOWNLOAD not in steps and self.storage.has_audio(
            bv_id, part, total_parts
        ):
            result["audio_path"] = self.storage.get_audio_path(bv_id, part, total_parts)

        try:
            for step in steps:
                runner = self.steps[step]
                self._set_progress(
                    bv_id,
                    current_step=runner.progress_step,
                    step_progress=0.0,
                )
                step_result = await runner.run(context, result)
                result.update(step_result.data)
                if step_result.cached:
                    cached_steps.append(f"{context.prefix}{step.value}")
                self._set_progress(
                    bv_id,
                    current_step=runner.progress_step,
                    step_progress=1.0,
                )
                await _to_thread(
                    self._update_metadata, bv_id, url, [result], parts, video_info
                )

            return result

        except DownloadError as e:
            raise ProcessError("download", e.code, e.message)
        except STTError as e:
            raise ProcessError("stt", e.code, e.message)

    def _handle_config_changes(
        self, bv_id: str, metadata: dict, total_parts: int, target_parts: list[int]
    ):
        old_stt = metadata.get("stt_model")
        old_llm = metadata.get("llm_model")

        stt_changed = old_stt and old_stt != settings.qwen_asr_model_path
        llm_changed = old_llm and old_llm != self._get_current_llm_model()

        if not stt_changed and not llm_changed:
            return

        logger.info(f"检测到配置变化: stt={stt_changed}, llm={llm_changed}")

        for part in target_parts:
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
        return settings.llm_model

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
                "source": get_source_name(url),
                "stt_model": settings.qwen_asr_model_path,
                "llm_model": self._get_current_llm_model(),
                "total_parts": len(parts) or 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if video_info:
            metadata["video"] = video_info
        elif "video" not in metadata:
            metadata["video"] = {}
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
            artifacts = self.storage.list_part_artifacts(bv_id, part_num, total_parts)
            update_dict = {
                "has_audio": artifacts[ArtifactKind.AUDIO.value],
                "has_transcript": artifacts[ArtifactKind.TRANSCRIPT.value],
                "has_translation": artifacts[ArtifactKind.TRANSLATION.value],
                "has_summary": artifacts[ArtifactKind.SUMMARY.value],
            }
            # Only update language/duration if result has them (not cached)
            if result.get("language") is not None:
                update_dict["language"] = result.get("language")
            if result.get("duration_seconds") is not None:
                update_dict["duration_seconds"] = result.get("duration_seconds")
            part_entry.update(update_dict)

        metadata["parts"] = sorted(parts_meta, key=lambda p: p["part"])
        self.storage.save_metadata(bv_id, metadata)
