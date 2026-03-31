from fastapi import APIRouter, HTTPException
from loguru import logger

from src.models.schemas import (
    ProcessRequest,
    ProcessResult,
    ErrorResponse,
    ErrorDetail,
    ProgressInfo,
)
from src.exceptions import ProcessError, DownloadError
from src.services.pipeline import ProcessingPipeline

router = APIRouter(prefix="/api/v1")
pipeline = ProcessingPipeline()


@router.post(
    "/process", response_model=ProcessResult, responses={400: {"model": ErrorResponse}}
)
async def process_video(request: ProcessRequest):
    try:
        result = await pipeline.process(
            url=request.url,
            translate=request.options.translate,
            summarize=request.options.summarize,
            force=request.options.force,
        )
        return ProcessResult(**result)
    except DownloadError as e:
        logger.error(f"下载校验失败 [{e.code}] {e.message}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(stage="download", code=e.code, message=e.message)
            ).model_dump(),
        )
    except ProcessError as e:
        logger.error(f"处理失败 [{e.stage}:{e.code}] {e.message}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(stage=e.stage, code=e.code, message=e.message)
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"未知错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    stage="unknown", code="INTERNAL_ERROR", message=str(e)
                )
            ).model_dump(),
        )


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "bili-digest"}


@router.get("/status/{bv_id}", response_model=ProgressInfo)
async def get_progress(bv_id: str):
    progress = pipeline.get_progress(bv_id)
    if progress:
        return progress
    # 没有活跃进度 → 检查是否已处理完成
    from src.utils.storage import ResultStorage

    storage = ResultStorage()
    metadata = storage.load_metadata(bv_id)
    if metadata:
        return ProgressInfo(
            bv_id=bv_id,
            status="done",
            current_step="done",
            step_progress=1.0,
            total_parts=len(metadata.get("parts", [])) or 1,
            current_part=1,
        )
    raise HTTPException(status_code=404, detail="视频不存在")
