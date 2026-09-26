import asyncio

from src.models.schemas import ProgressInfo
from src.services.jobs import JobManager


class FakePipeline:
    def __init__(self):
        self.calls = 0

    async def process_request(self, request):
        self.calls += 1
        await asyncio.sleep(0)
        return {
            "url": request.url,
            "transcript": "hello",
            "language": "en",
        }

    def get_progress(self, bv_id):
        return ProgressInfo(
            bv_id=bv_id,
            status="processing",
            current_step="stt",
            step_progress=0.5,
        )


def test_job_manager_deduplicates_active_video():
    async def scenario():
        pipeline = FakePipeline()
        manager = JobManager(pipeline)
        request = type("Request", (), {"url": "BV1xx411c7mD"})()

        first = await manager.submit(request)
        second = await manager.submit(request)
        await first.task

        assert first.job_id == second.job_id
        assert pipeline.calls == 1
        assert first.status == "done"
        assert first.result["transcript"] == "hello"

    asyncio.run(scenario())
