import hashlib
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

from loguru import logger

from src.exceptions import DownloadError

BV_PATTERN = re.compile(r"^BV[1-9A-HJ-NP-Za-km-z]{10}$")
BILI_URL_PATTERN = re.compile(
    r"https?://(www\.)?bilibili\.com/video/(BV[1-9A-HJ-NP-Za-km-z]{10})"
)

SUPPORTED_DOMAINS = [
    "bilibili.com",
    "youtube.com",
    "youtu.be",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "reddit.com",
    "soundcloud.com",
    "vimeo.com",
    "twitch.tv",
    "instagram.com",
    "music.163.com",
    "ximalaya.com",
    "xiaoyuzhoufm.com",
]


@dataclass
class PartInfo:
    part: int
    title: str
    duration: float | None = None


def _is_supported_url(url: str) -> bool:
    """检查 URL 是否匹配白名单域名。"""
    try:
        host = urlparse(url).hostname or ""
        return any(host.endswith(d) for d in SUPPORTED_DOMAINS)
    except Exception:
        return False


def extract_video_id(url_or_id: str) -> str:
    """提取视频标识符。B站返回BV号，其他站点返回 URL hash。"""
    # 纯 BV 号
    if BV_PATTERN.match(url_or_id):
        return url_or_id

    # B站 URL
    match = BILI_URL_PATTERN.match(url_or_id)
    if match:
        return match.group(2)

    # 其他白名单 URL → 用 hash 作为稳定 ID
    if _is_supported_url(url_or_id):
        return hashlib.md5(url_or_id.encode()).hexdigest()[:12]

    raise DownloadError("INVALID_URL", f"不支持的链接: {url_or_id}")


def validate_input(url_or_id: str) -> str:
    """校验输入，返回规范 URL。"""
    # 纯 BV 号 → 补全为 B站 URL
    if BV_PATTERN.match(url_or_id):
        return f"https://www.bilibili.com/video/{url_or_id}"

    # B站 URL（可能带查询参数等）→ 提取 BV 号重建
    # 先尝试宽松匹配，支持带 ?query 的 URL
    bili_match = re.search(r"(BV[1-9A-HJ-NP-Za-km-z]{10})", url_or_id)
    if bili_match and "bilibili.com" in url_or_id:
        return f"https://www.bilibili.com/video/{bili_match.group(1)}"

    # 其他白名单 URL → 直接返回
    if _is_supported_url(url_or_id):
        return url_or_id

    raise DownloadError("INVALID_URL", f"不支持的链接: {url_or_id}")


def get_source_name(url: str) -> str:
    """从 URL 提取来源站点名称。"""
    host = urlparse(url).hostname or ""
    for domain in SUPPORTED_DOMAINS:
        if host.endswith(domain):
            return domain.split(".")[-2]  # youtube, bilibili, twitter...
    return "unknown"


def get_parts(url_or_id: str) -> list[PartInfo]:
    """获取视频分P信息。"""
    video_url = validate_input(url_or_id)
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
