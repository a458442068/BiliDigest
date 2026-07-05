from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from src.models.schemas import (
    ProcessRequest,
    ProcessResult,
    ErrorResponse,
    ErrorDetail,
    ProgressInfo,
)
from src.exceptions import ProcessError, DownloadError
from src.models.domain import ProcessingRequest
from src.services.pipeline import ProcessingPipeline
from src.utils.export import ExportError, ExportService

router = APIRouter(prefix="/api/v1")
pipeline = ProcessingPipeline()
export_service = ExportService()


def _raise_export_error(e: ExportError):
    raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/process", response_model=ProcessResult, responses={400: {"model": ErrorResponse}}
)
async def process_video(request: ProcessRequest):
    try:
        result = await pipeline.process_request(
            ProcessingRequest(
                url=request.url,
                translate=request.options.translate,
                summarize=request.options.summarize,
                force=request.options.force,
                from_step=request.options.from_step,
            )
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
    raise HTTPException(status_code=404, detail="视频不存在")


@router.get("/export/{bv_id}/srt", response_class=PlainTextResponse)
async def export_srt(bv_id: str, part: int = Query(default=1)):
    try:
        return PlainTextResponse(
            export_service.srt(bv_id, part), media_type="text/plain"
        )
    except ExportError as e:
        _raise_export_error(e)


@router.get("/export/{bv_id}/vtt", response_class=PlainTextResponse)
async def export_vtt(bv_id: str, part: int = Query(default=1)):
    try:
        return PlainTextResponse(export_service.vtt(bv_id, part), media_type="text/vtt")
    except ExportError as e:
        _raise_export_error(e)


@router.get("/export/{bv_id}/txt", response_class=PlainTextResponse)
async def export_txt(bv_id: str, part: int = Query(default=1)):
    try:
        return PlainTextResponse(
            export_service.txt(bv_id, part), media_type="text/plain"
        )
    except ExportError as e:
        _raise_export_error(e)


@router.get("/export/{bv_id}/md", response_class=PlainTextResponse)
async def export_md(bv_id: str, part: int = Query(default=1)):
    try:
        return PlainTextResponse(
            export_service.md(bv_id, part), media_type="text/markdown"
        )
    except ExportError as e:
        _raise_export_error(e)


@router.get("/export/{bv_id}/json")
async def export_json(bv_id: str, part: int = Query(default=1)):
    try:
        return JSONResponse(export_service.json(bv_id, part))
    except ExportError as e:
        _raise_export_error(e)
