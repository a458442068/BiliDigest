from src.models.domain import ArtifactKind


DEFAULT_STATUS_FILTER = "all"
DEFAULT_OPTION_FILTER = "all"

SORTABLE_FIELDS = (
    "updated_at",
    "title",
    "source",
    "uploader",
    "duration",
    "language",
    "status",
    "size_bytes",
)


def _format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _sort_value(video: dict, field: str):
    value = video.get(field)
    return (value is None, value)


def _matches_filters(
    video: dict, q: str, status: str, source: str, language: str, artifact: str
) -> bool:
    if q:
        q_lower = q.lower()
        searchable = (
            video.get("title", ""),
            video.get("uploader", ""),
            video.get("bv_id", ""),
        )
        if not any(q_lower in value.lower() for value in searchable):
            return False

    if status != DEFAULT_STATUS_FILTER:
        if status == "processing":
            if video.get("status") not in ("queued", "processing"):
                return False
        elif video.get("status") != status:
            return False

    if source != DEFAULT_OPTION_FILTER and video.get("source") != source:
        return False

    if language != DEFAULT_OPTION_FILTER and video.get("language") != language:
        return False

    if artifact != DEFAULT_OPTION_FILTER:
        artifact_field = {
            "transcript": "has_transcript",
            "translation": "has_translation",
            "summary": "has_summary",
        }.get(artifact)
        if artifact_field and not video.get(artifact_field):
            return False

    return True


def _build_list_stats(videos: list[dict]) -> dict:
    total_size = sum(video.get("size_bytes") or 0 for video in videos)
    latest_update = max((video.get("updated_at") or "" for video in videos), default="")
    return {
        "total": len(videos),
        "processing": sum(
            1 for video in videos if video.get("status") in ("queued", "processing")
        ),
        "error": sum(1 for video in videos if video.get("status") == "error"),
        "done": sum(1 for video in videos if video.get("status") == "done"),
        "total_size_label": _format_size(total_size),
        "latest_update": latest_update[:16] if latest_update else "-",
    }


def _build_filter_options(videos: list[dict]) -> dict:
    return {
        "sources": sorted({video.get("source") for video in videos if video.get("source")}),
        "languages": sorted(
            {video.get("language") for video in videos if video.get("language")}
        ),
        "statuses": [
            ("all", "全部状态"),
            ("processing", "处理中"),
            ("done", "已完成"),
            ("error", "失败"),
        ],
        "artifacts": [
            ("all", "全部产物"),
            ("transcript", "有转写"),
            ("translation", "有翻译"),
            ("summary", "有摘要"),
        ],
    }


def build_video_dashboard(
    storage,
    q: str,
    status: str,
    source: str,
    language: str,
    artifact: str,
    sort: str,
    order: str,
) -> dict:
    videos = storage.list_videos()

    allowed_statuses = {"all", "queued", "processing", "done", "error"}
    status = status if status in allowed_statuses else DEFAULT_STATUS_FILTER
    allowed_artifacts = {"all", "transcript", "translation", "summary"}
    artifact = artifact if artifact in allowed_artifacts else DEFAULT_OPTION_FILTER

    filtered_videos = [
        video
        for video in videos
        if _matches_filters(video, q, status, source, language, artifact)
    ]

    if sort in SORTABLE_FIELDS:
        filtered_videos.sort(
            key=lambda v: _sort_value(v, sort), reverse=(order == "desc")
        )

    filters = {
        "q": q,
        "status": status,
        "source": source,
        "language": language,
        "artifact": artifact,
        "sort": sort,
        "order": order,
    }
    active_filters = any(
        (
            q,
            status != DEFAULT_STATUS_FILTER,
            source != DEFAULT_OPTION_FILTER,
            language != DEFAULT_OPTION_FILTER,
            artifact != DEFAULT_OPTION_FILTER,
        )
    )

    return {
        "videos": filtered_videos,
        "stats": _build_list_stats(videos),
        "filter_options": _build_filter_options(videos),
        "filters": filters,
        "active_filters": active_filters,
        "result_count": len(filtered_videos),
    }


def build_video_list(storage, q: str, sort: str, order: str) -> list[dict]:
    return build_video_dashboard(
        storage,
        q=q,
        status=DEFAULT_STATUS_FILTER,
        source=DEFAULT_OPTION_FILTER,
        language=DEFAULT_OPTION_FILTER,
        artifact=DEFAULT_OPTION_FILTER,
        sort=sort,
        order=order,
    )["videos"]


def build_detail_context(storage, pipeline, bv_id: str, metadata: dict) -> dict:
    parts = metadata.get("parts", [])
    total_parts = len(parts) or 1
    display_parts = parts or [
        {"part": 1, "title": metadata.get("video", {}).get("title", "")}
    ]

    contents = [
        _build_part_content(storage, bv_id, part_meta, total_parts, index)
        for index, part_meta in enumerate(display_parts)
    ]

    progress = pipeline.get_progress(bv_id)
    is_processing = bool(progress and progress.status in ("queued", "processing"))
    progress_data = (
        progress.model_dump()
        if progress
        else {
            "status": metadata.get("status", "done"),
            "current_step": metadata.get("current_step", "done"),
            "step_progress": metadata.get("step_progress", 1.0),
            "total_parts": total_parts,
            "current_part": metadata.get("current_part", 1),
        }
    )
    video = dict(metadata.get("video", {}))
    if not video.get("duration"):
        duration = sum(
            part.get("duration_seconds") or part.get("duration") or 0
            for part in display_parts
        )
        video["duration"] = duration or None

    return {
        "bv_id": bv_id,
        "metadata": metadata,
        "video": video,
        "parts": parts,
        "contents": contents,
        "total_parts": total_parts,
        "is_processing": is_processing,
        "progress": progress_data,
    }


def _build_part_content(
    storage, bv_id: str, part_meta: dict, total_parts: int, index: int
) -> dict:
    part = part_meta.get("part", index + 1)
    artifacts = storage.list_part_artifacts(bv_id, part, total_parts)
    duration_seconds = part_meta.get("duration_seconds") or part_meta.get("duration")
    part_data = {
        "part": part,
        "title": part_meta.get("title") or f"分P {part}",
        "duration_seconds": duration_seconds,
        "duration_label": f"{duration_seconds:.0f}秒" if duration_seconds else "-",
        "language": part_meta.get("language"),
        "has_audio": artifacts[ArtifactKind.AUDIO.value],
        "has_transcript": artifacts[ArtifactKind.TRANSCRIPT.value],
        "has_translation": artifacts[ArtifactKind.TRANSLATION.value],
        "has_summary": artifacts[ArtifactKind.SUMMARY.value],
    }
    try:
        part_data["transcript"] = storage.load_artifact(
            bv_id, part, total_parts, ArtifactKind.TRANSCRIPT
        )
    except FileNotFoundError:
        part_data["transcript"] = None
    try:
        part_data["translation"] = storage.load_artifact(
            bv_id, part, total_parts, ArtifactKind.TRANSLATION
        )
    except FileNotFoundError:
        part_data["translation"] = None

    try:
        part_data["transcript_clean"] = storage.load_artifact(
            bv_id, part, total_parts, ArtifactKind.TRANSCRIPT_CLEAN
        )
    except FileNotFoundError:
        part_data["transcript_clean"] = None
    try:
        part_data["summary"] = storage.load_artifact(
            bv_id, part, total_parts, ArtifactKind.SUMMARY
        )
    except FileNotFoundError:
        part_data["summary"] = None
    return part_data
