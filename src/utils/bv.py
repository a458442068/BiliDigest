import re
import subprocess
from dataclasses import dataclass

from loguru import logger

from src.exceptions import DownloadError


BV_PATTERN = re.compile(r"^BV[1-9A-HJ-NP-Za-km-z]{10}$")
URL_PATTERN = re.compile(
    r"https?://(www\.)?bilibili\.com/video/(BV[1-9A-HJ-NP-Za-km-z]{10})"
)


@dataclass
class PartInfo:
    part: int
    title: str
    duration: float | None = None


def extract_bv_id(url_or_bv: str) -> str:
    if BV_PATTERN.match(url_or_bv):
        return url_or_bv
    match = URL_PATTERN.match(url_or_bv)
    if match:
        return match.group(2)
    if "bilibili.com" in url_or_bv:
        raise DownloadError("INVALID_URL", f"无效的B站URL: {url_or_bv}")
    raise DownloadError("INVALID_BV_FORMAT", f"无效的BV号: {url_or_bv}")


def validate_input(url_or_bv: str) -> str:
    bv_id = extract_bv_id(url_or_bv)
    return f"https://www.bilibili.com/video/{bv_id}"


def get_parts(url_or_bv: str) -> list[PartInfo]:
    video_url = validate_input(url_or_bv)
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print",
        "%(playlist_index)s|%(title)s|%(duration)s",
        "--no-warnings",
        video_url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return [PartInfo(part=1, title="")]
        parts = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                idx, title, duration = line.split("|", 2)
                parts.append(
                    PartInfo(
                        part=int(idx),
                        title=title,
                        duration=float(duration) if duration != "NA" else None,
                    )
                )
        return parts if parts else [PartInfo(part=1, title="")]
    except Exception:
        return [PartInfo(part=1, title="")]
