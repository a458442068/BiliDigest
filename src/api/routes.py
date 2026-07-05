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
from src.services.pipeline import ProcessingPipeline
from src.utils.storage import ResultStorage

router = APIRouter(prefix="/api/v1")
pipeline = ProcessingPipeline()


def _load_export_context(bv_id: str, part: int) -> tuple[ResultStorage, dict, int]:
    storage = ResultStorage()
    try:
        metadata = storage.load_metadata(bv_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not metadata:
        raise HTTPException(status_code=404, detail="视频不存在")
    total_parts = len(metadata.get("parts", [])) or 1
    if part < 1 or part > total_parts:
        raise HTTPException(status_code=400, detail=f"分P不存在: {part}")
    return storage, metadata, total_parts


def _load_part_texts(
    storage: ResultStorage, bv_id: str, part: int, total_parts: int
) -> dict:
    def read_or_none(loader):
        try:
            return loader(bv_id, part, total_parts)
        except FileNotFoundError:
            return None

    summary_data = storage.load_summary(bv_id, part, total_parts)
    if not isinstance(summary_data, dict):
        summary_data = {"summary": summary_data} if summary_data else {}
    return {
        "transcript": read_or_none(storage.load_transcript),
        "translation": read_or_none(storage.load_translation),
        "transcript_clean": summary_data.get("transcript_clean"),
        "summary": summary_data.get("summary"),
    }


def _part_metadata(metadata: dict, part: int) -> dict:
    return next((p for p in metadata.get("parts", []) if p.get("part") == part), {})


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
    raise HTTPException(status_code=404, detail="视频不存在")


@router.get("/export/{bv_id}/srt", response_class=PlainTextResponse)
async def export_srt(bv_id: str, part: int = Query(default=1)):
    from src.utils.subtitle import segments_to_srt, transcript_to_srt

    storage, metadata, total_parts = _load_export_context(bv_id, part)
    segments = storage.load_segments(bv_id, part, total_parts)
    if segments:
        content = segments_to_srt(segments)
    else:
        transcript = storage.load_transcript(bv_id, part, total_parts)
        part_meta = _part_metadata(metadata, part)
        duration = part_meta.get("duration_seconds", 0) or 0
        content = transcript_to_srt(transcript, duration)

    if not content:
        raise HTTPException(status_code=404, detail="无可用字幕数据")

    return PlainTextResponse(content, media_type="text/plain")


@router.get("/export/{bv_id}/vtt", response_class=PlainTextResponse)
async def export_vtt(bv_id: str, part: int = Query(default=1)):
    from src.utils.subtitle import segments_to_vtt, transcript_to_vtt

    storage, metadata, total_parts = _load_export_context(bv_id, part)
    segments = storage.load_segments(bv_id, part, total_parts)
    if segments:
        content = segments_to_vtt(segments)
    else:
        transcript = storage.load_transcript(bv_id, part, total_parts)
        part_meta = _part_metadata(metadata, part)
        duration = part_meta.get("duration_seconds", 0) or 0
        content = transcript_to_vtt(transcript, duration)

    if not content:
        raise HTTPException(status_code=404, detail="无可用字幕数据")

    return PlainTextResponse(content, media_type="text/vtt")


@router.get("/export/{bv_id}/txt", response_class=PlainTextResponse)
async def export_txt(bv_id: str, part: int = Query(default=1)):
    storage, metadata, total_parts = _load_export_context(bv_id, part)
    texts = _load_part_texts(storage, bv_id, part, total_parts)
    part_meta = _part_metadata(metadata, part)
    sections = [
        ("标题", metadata.get("video", {}).get("title") or bv_id),
        ("分P", str(part_meta.get("title") or part)),
        ("文字稿", texts.get("transcript")),
        ("翻译", texts.get("translation")),
        ("整理版", texts.get("transcript_clean")),
        ("摘要", texts.get("summary")),
    ]
    content = "\n\n".join(f"【{title}】\n{body}" for title, body in sections if body)
    if not content:
        raise HTTPException(status_code=404, detail="无可导出内容")
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/export/{bv_id}/md", response_class=PlainTextResponse)
async def export_md(bv_id: str, part: int = Query(default=1)):
    storage, metadata, total_parts = _load_export_context(bv_id, part)
    texts = _load_part_texts(storage, bv_id, part, total_parts)
    title = metadata.get("video", {}).get("title") or bv_id
    part_meta = _part_metadata(metadata, part)
    lines = [f"# {title}", "", f"- 分P: {part_meta.get('title') or part}"]
    for heading, body in (
        ("文字稿", texts.get("transcript")),
        ("翻译", texts.get("translation")),
        ("整理版", texts.get("transcript_clean")),
        ("摘要", texts.get("summary")),
    ):
        if body:
            lines.extend(["", f"## {heading}", "", body])
    content = "\n".join(lines).strip()
    if not content:
        raise HTTPException(status_code=404, detail="无可导出内容")
    return PlainTextResponse(content, media_type="text/markdown")


@router.get("/export/{bv_id}/json")
async def export_json(bv_id: str, part: int = Query(default=1)):
    storage, metadata, total_parts = _load_export_context(bv_id, part)
    texts = _load_part_texts(storage, bv_id, part, total_parts)
    return JSONResponse(
        {
            "bv_id": bv_id,
            "part": part,
            "metadata": metadata,
            "part_metadata": _part_metadata(metadata, part),
            **texts,
        }
    )
