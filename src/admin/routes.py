from pathlib import Path

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from src.api.routes import pipeline
from src.admin.view_models import build_detail_context, build_video_dashboard
from src.models.domain import ProcessingRequest
from src.utils.storage import ResultStorage

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
storage = ResultStorage()


def _load_metadata_or_404(bv_id: str) -> dict:
    try:
        metadata = storage.load_metadata(bv_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not metadata:
        raise HTTPException(status_code=404, detail="视频不存在")
    return metadata


def _refresh_metadata_background(bv_id: str):
    try:
        pipeline.refresh_metadata(bv_id)
    except Exception as e:
        logger.warning(f"后台刷新视频信息失败 [{bv_id}]: {e}")


@router.get("/", response_class=HTMLResponse)
async def video_list(
    request: Request,
    q: str = "",
    status: str = "all",
    source: str = "all",
    language: str = "all",
    artifact: str = "all",
    sort: str = "updated_at",
    order: str = "desc",
):
    context = build_video_dashboard(
        storage,
        q=q,
        status=status,
        source=source,
        language=language,
        artifact=artifact,
        sort=sort,
        order=order,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        {"request": request, **context},
    )


@router.get("/video/{bv_id}", response_class=HTMLResponse)
async def video_detail(request: Request, bv_id: str):
    metadata = _load_metadata_or_404(bv_id)
    context = build_detail_context(storage, pipeline, bv_id, metadata)

    return templates.TemplateResponse(
        request,
        "detail.html",
        {"request": request, **context},
    )


@router.post("/video/{bv_id}/delete")
async def video_delete(bv_id: str):
    try:
        deleted = storage.delete_video(bv_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="视频不存在")
    pipeline.clear_progress(bv_id)
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/video/{bv_id}/refresh-metadata")
async def video_refresh_metadata(bv_id: str, background_tasks: BackgroundTasks):
    _load_metadata_or_404(bv_id)
    background_tasks.add_task(_refresh_metadata_background, bv_id)
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)


@router.post("/video/{bv_id}/reprocess")
async def video_reprocess(bv_id: str, background_tasks: BackgroundTasks):
    metadata = _load_metadata_or_404(bv_id)
    url = metadata.get("url", f"https://www.bilibili.com/video/{bv_id}")
    pipeline.mark_queued(bv_id, len(metadata.get("parts", [])) or 1)
    background_tasks.add_task(
        pipeline.process_request,
        ProcessingRequest(
            url=url,
            translate=True,
            summarize=True,
            force=True,
        ),
    )
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)


_STEPS_SEQUENCE = ["download", "stt", "translation", "summary"]


@router.post("/video/{bv_id}/reprocess/{from_step}")
async def video_reprocess_from(
    bv_id: str,
    from_step: str,
    background_tasks: BackgroundTasks,
    part: int | None = Query(default=None),
):
    if from_step not in _STEPS_SEQUENCE:
        raise HTTPException(status_code=400, detail=f"无效的步骤: {from_step}")

    metadata = _load_metadata_or_404(bv_id)

    parts = metadata.get("parts", [])
    total_parts = len(parts) or 1
    target_parts = [part] if part else list(range(1, total_parts + 1))
    if part is not None and (part < 1 or part > total_parts):
        raise HTTPException(status_code=400, detail=f"分P不存在: {part}")

    for part_num in target_parts:
        storage.delete_artifacts(bv_id, part_num, total_parts, from_step)

    url = metadata.get("url", f"https://www.bilibili.com/video/{bv_id}")
    pipeline.mark_queued(bv_id, total_parts)
    background_tasks.add_task(
        pipeline.process_request,
        ProcessingRequest(
            url=url,
            translate=True,
            summarize=True,
            target_parts={part} if part is not None else None,
            from_step=from_step,
        ),
    )
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)
