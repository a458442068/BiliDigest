from src.models.domain import ArtifactKind


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


def _sort_value(video: dict, field: str):
    value = video.get(field)
    return (value is None, value)


def build_video_list(storage, q: str, sort: str, order: str) -> list[dict]:
    videos = storage.list_videos()
    if q:
        q_lower = q.lower()
        videos = [
            v
            for v in videos
            if q_lower in v["title"].lower() or q_lower in v["uploader"].lower()
        ]
    if sort in SORTABLE_FIELDS:
        videos.sort(key=lambda v: _sort_value(v, sort), reverse=(order == "desc"))
    return videos


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

    return {
        "bv_id": bv_id,
        "metadata": metadata,
        "video": metadata.get("video", {}),
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
    part_data = {
        "part": part,
        "title": part_meta.get("title") or f"分P {part}",
        "duration_seconds": part_meta.get("duration_seconds")
        or part_meta.get("duration"),
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
