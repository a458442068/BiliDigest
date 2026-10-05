import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from src.models.domain import ProcessingRequest, VideoRef
from src.services.pipeline import ProcessingPipeline


@dataclass
class JobRecord:
    job_id: str
    bv_id: str
    request: ProcessingRequest
    request_signature: tuple = ()
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict | None = None
    error: str | None = None
    error_detail: dict | None = None
    task: asyncio.Task | None = None


class JobManager:
    """Lightweight in-process task manager for the local single-user deployment."""

    def __init__(self, pipeline: ProcessingPipeline, retention_days: int = 7):
        self.pipeline = pipeline
        self.jobs: dict[str, JobRecord] = {}
        self.active_by_video: dict[str, str] = {}
        self._lock = asyncio.Lock()
        storage = getattr(pipeline, "storage", None)
        self._path = storage.result_dir / "jobs.json" if storage else None
        self._retention_seconds = retention_days * 86400
        self._load()

    def _load(self):
        if self._path is None or not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        now = datetime.now(timezone.utc).timestamp()
        for item in raw:
            try:
                updated = datetime.fromisoformat(item["updated_at"]).timestamp()
                if now - updated > self._retention_seconds:
                    continue
                job = JobRecord(
                    job_id=item["job_id"], bv_id=item["bv_id"],
                    request=ProcessingRequest(**item["request"]),
                    request_signature=tuple(item.get("request_signature", ())),
                    status=item.get("status", "error"),
                    created_at=item["created_at"], updated_at=item["updated_at"],
                    result=item.get("result"), error=item.get("error"),
                    error_detail=item.get("error_detail"),
                )
                if job.status in {"queued", "processing"}:
                    job.status = "error"
                    job.error = "服务重启导致任务中断"
                    job.error_detail = {"stage": "job", "code": "INTERRUPTED", "message": job.error}
                self.jobs[job.job_id] = job
            except (KeyError, TypeError, ValueError):
                continue

    def _save(self):
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for job in self.jobs.values():
            data.append({
                "job_id": job.job_id, "bv_id": job.bv_id,
                "request": {"url": job.request.url,
                    "target_parts": sorted(job.request.target_parts) if job.request.target_parts is not None else None,
                    "from_step": job.request.from_step.value if job.request.from_step else None,
                    "force": job.request.force, "translate": job.request.translate,
                    "summarize": job.request.summarize, "summary_template": job.request.summary_template},
                "request_signature": list(job.request_signature), "status": job.status,
                "created_at": job.created_at, "updated_at": job.updated_at,
                "result": job.result, "error": job.error, "error_detail": job.error_detail,
            })
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path)

    async def submit(self, request: ProcessingRequest) -> JobRecord:
        video_ref = VideoRef.from_input(request.url)
        signature = self._signature(video_ref.bv_id, request)
        async with self._lock:
            existing_job_id = self.active_by_video.get(video_ref.bv_id)
            if existing_job_id:
                existing = self.jobs.get(existing_job_id)
                if existing and existing.status in {"queued", "processing"}:
                    if existing.request_signature != signature:
                        raise ValueError("该视频正在处理，当前请求选项与已有任务不同")
                    return existing

            job = JobRecord(
                job_id=uuid4().hex,
                bv_id=video_ref.bv_id,
                request=request,
                request_signature=signature,
            )
            self.jobs[job.job_id] = job
            self.active_by_video[job.bv_id] = job.job_id
            job.task = asyncio.create_task(self._run(job), name=f"process-{job.bv_id}")
            self._save()
            return job

    @staticmethod
    def _signature(bv_id: str, request: ProcessingRequest) -> tuple:
        return (
            bv_id,
            tuple(sorted(request.target_parts or set())),
            request.from_step.value if request.from_step else None,
            request.force,
            request.translate,
            request.summarize,
            request.summary_template,
        )

    async def _run(self, job: JobRecord):
        job.status = "processing"
        job.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            job.result = await self.pipeline.process_request(job.request)
            job.status = "done"
        except Exception as exc:
            job.error = getattr(exc, "message", str(exc)) or "处理失败"
            job.error_detail = {"stage": getattr(exc, "stage", "unknown"), "code": getattr(exc, "code", "INTERNAL_ERROR"), "message": job.error}
            job.status = "error"
        finally:
            job.updated_at = datetime.now(timezone.utc).isoformat()
            async with self._lock:
                if self.active_by_video.get(job.bv_id) == job.job_id:
                    self.active_by_video.pop(job.bv_id, None)
                self._save()

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    def progress(self, job: JobRecord):
        progress = self.pipeline.get_progress(job.bv_id)
        if progress:
            return progress
        return {
            "bv_id": job.bv_id,
            "status": job.status,
            "current_step": "done" if job.status == "done" else "unknown",
            "step_progress": 1.0 if job.status == "done" else 0.0,
            "total_parts": 1,
            "current_part": 1,
            "error": job.error,
        }
