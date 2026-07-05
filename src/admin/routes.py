from pathlib import Path

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.api.routes import pipeline
from src.admin.view_models import build_detail_context, build_video_list
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


@router.get("/", response_class=HTMLResponse)
async def video_list(
    request: Request, q: str = "", sort: str = "updated_at", order: str = "desc"
):
    videos = build_video_list(storage, q, sort, order)
    return templates.TemplateResponse(
        request,
        "list.html",
        {"request": request, "videos": videos, "q": q, "sort": sort, "order": order},
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


@router.post("/video/{bv_id}/reprocess")
async def video_reprocess(bv_id: str, background_tasks: BackgroundTasks):
    metadata = _load_metadata_or_404(bv_id)
    url = metadata.get("url", f"https://www.bilibili.com/video/{bv_id}")
    pipeline.mark_queued(bv_id, len(metadata.get("parts", [])) or 1)
    background_tasks.add_task(
        pipeline.process,
        url=url,
        translate=True,
        summarize=True,
        force=True,
    )
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)


# 从指定步骤开始重跑：删除该步骤及下游文件，再 force 重跑
_STEPS_SEQUENCE = ["download", "stt", "translation", "summary"]


def _delete_step_files(bv_id: str, step: str, part: int, total_parts: int):
    """删除指定步骤的产出文件。"""
    prefix = storage._prefix(part, total_parts)
    file_map = {
        "stt": [f"{prefix}transcript.txt", f"{prefix}segments.json"],
        "translation": [f"{prefix}translation.txt"],
        "summary": [f"{prefix}summary.txt", f"{prefix}transcript_clean.txt"],
    }
    filenames = file_map.get(step, [])
    for filename in filenames:
        path = storage.get_dir(bv_id) / filename
        if path.exists():
            path.unlink()


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

    # 删除 from_step 及其下游步骤的文件
    start_idx = _STEPS_SEQUENCE.index(from_step)
    for step in _STEPS_SEQUENCE[start_idx:]:
        if step == "download":
            continue  # 不删除音频，让 pipeline 跳过下载
        for part_num in target_parts:
            _delete_step_files(bv_id, step, part_num, total_parts)

    url = metadata.get("url", f"https://www.bilibili.com/video/{bv_id}")
    pipeline.mark_queued(bv_id, total_parts)
    background_tasks.add_task(
        pipeline.process,
        url=url,
        translate=True,
        summarize=True,
        target_parts={part} if part is not None else None,
    )
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)
