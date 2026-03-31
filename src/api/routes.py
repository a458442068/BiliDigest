from fastapi import APIRouter, HTTPException
from loguru import logger

from src.models.schemas import ProcessRequest, ProcessResult, ErrorResponse, ErrorDetail
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
