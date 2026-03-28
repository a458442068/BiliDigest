from pathlib import Path

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.services.pipeline import ProcessingPipeline
from src.utils.storage import ResultStorage

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
storage = ResultStorage()
pipeline = ProcessingPipeline()


@router.get("/", response_class=HTMLResponse)
async def video_list(
    request: Request, q: str = "", sort: str = "updated_at", order: str = "desc"
):
    videos = storage.list_videos()
    if q:
        q_lower = q.lower()
        videos = [
            v
            for v in videos
            if q_lower in v["title"].lower() or q_lower in v["uploader"].lower()
        ]
    if sort in ("updated_at", "title", "uploader", "duration", "language"):
        videos.sort(
            key=lambda v: v.get(sort, ""),
            reverse=(order == "desc"),
        )
    return templates.TemplateResponse(
        "list.html",
        {"request": request, "videos": videos, "q": q, "sort": sort, "order": order},
    )


@router.get("/video/{bv_id}", response_class=HTMLResponse)
async def video_detail(request: Request, bv_id: str):
    metadata = storage.load_metadata(bv_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="视频不存在")

    parts = metadata.get("parts", [])
    total_parts = len(parts)

    contents = []
    for part in range(1, total_parts + 1):
        part_data = {"part": part}
        try:
            part_data["transcript"] = storage.load_transcript(bv_id, part, total_parts)
        except Exception:
            part_data["transcript"] = None
        try:
            part_data["translation"] = storage.load_translation(
                bv_id, part, total_parts
            )
        except Exception:
            part_data["translation"] = None
        summary = storage.load_summary(bv_id, part, total_parts)
        if isinstance(summary, dict):
            part_data["transcript_clean"] = summary.get("transcript_clean")
            part_data["summary"] = summary.get("summary")
        else:
            part_data["transcript_clean"] = None
            part_data["summary"] = summary if summary else None
        contents.append(part_data)

    return templates.TemplateResponse(
        "detail.html",
        {
            "request": request,
            "bv_id": bv_id,
            "metadata": metadata,
            "video": metadata.get("video", {}),
            "parts": parts,
            "contents": contents,
            "total_parts": total_parts,
        },
    )


@router.post("/video/{bv_id}/delete")
async def video_delete(bv_id: str):
    if not storage.delete_video(bv_id):
        raise HTTPException(status_code=404, detail="视频不存在")
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/video/{bv_id}/reprocess")
async def video_reprocess(bv_id: str, background_tasks: BackgroundTasks):
    metadata = storage.load_metadata(bv_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="视频不存在")
    url = metadata.get("url", f"https://www.bilibili.com/video/{bv_id}")
    background_tasks.add_task(
        pipeline.process,
        url=url,
        translate=True,
        summarize=True,
        force=True,
    )
    return RedirectResponse(url=f"/admin/video/{bv_id}", status_code=303)
