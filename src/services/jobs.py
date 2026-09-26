import asyncio
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
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: dict | None = None
    error: str | None = None
    task: asyncio.Task | None = None


class JobManager:
    """Lightweight in-process task manager for the local single-user deployment."""

    def __init__(self, pipeline: ProcessingPipeline):
        self.pipeline = pipeline
        self.jobs: dict[str, JobRecord] = {}
        self.active_by_video: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def submit(self, request: ProcessingRequest) -> JobRecord:
        video_ref = VideoRef.from_input(request.url)
        async with self._lock:
            existing_job_id = self.active_by_video.get(video_ref.bv_id)
            if existing_job_id:
                existing = self.jobs.get(existing_job_id)
                if existing and existing.status in {"queued", "processing"}:
                    return existing

            job = JobRecord(
                job_id=uuid4().hex,
                bv_id=video_ref.bv_id,
                request=request,
            )
            self.jobs[job.job_id] = job
            self.active_by_video[job.bv_id] = job.job_id
            job.task = asyncio.create_task(self._run(job), name=f"process-{job.bv_id}")
            return job

    async def _run(self, job: JobRecord):
        job.status = "processing"
        job.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            job.result = await self.pipeline.process_request(job.request)
            job.status = "done"
        except Exception as exc:
            job.error = getattr(exc, "message", str(exc)) or "处理失败"
            job.status = "error"
        finally:
            job.updated_at = datetime.now(timezone.utc).isoformat()
            async with self._lock:
                if self.active_by_video.get(job.bv_id) == job.job_id:
                    self.active_by_video.pop(job.bv_id, None)

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
