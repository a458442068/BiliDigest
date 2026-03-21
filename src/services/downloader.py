import json
import re
import subprocess
from pathlib import Path

from loguru import logger

from src.config import settings
from src.exceptions import DownloadError
from src.utils.audio import AudioFormatHandler
from src.utils.bv import validate_input, extract_bv_id


class BilibiliDownloader:
    def __init__(self, output_dir: str = "/tmp/stt_server"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url_or_bv: str) -> dict:
        video_url = validate_input(url_or_bv)
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--no-warnings",
            video_url,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )
            if result.returncode != 0:
                logger.warning(f"获取视频信息失败: {result.stderr[:200]}")
                return {}
            info = json.loads(result.stdout)
            return {
                "title": info.get("fulltitle") or info.get("title", ""),
                "description": info.get("description", ""),
                "uploader": info.get("uploader", ""),
                "upload_date": info.get("upload_date", ""),
            }
        except Exception as e:
            logger.warning(f"获取视频信息异常: {e}")
            return {}

    def download(self, url_or_bv: str, part: int = 1) -> str:
        video_url = validate_input(url_or_bv)
        bv_id = extract_bv_id(url_or_bv)
        output_template = str(self.output_dir / f"{bv_id}_P{part}.%(ext)s")

        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "-o",
            output_template,
            "--socket-timeout",
            "30",
        ]

        if part > 1:
            cmd.extend(["--playlist-items", str(part)])
        else:
            cmd.append("--no-playlist")

        if settings.bilibili_cookie:
            cookie_file = self.output_dir / "cookie.txt"
            cookie_file.write_text(settings.bilibili_cookie)
            cmd.extend(["--cookies", str(cookie_file)])

        cmd.append(video_url)

        logger.info(f"开始下载: {video_url} (分P: {part})")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )

            if result.returncode != 0:
                stderr = result.stderr.lower()
                if "login" in stderr or "cookie" in stderr:
                    raise DownloadError(
                        "AUTH_REQUIRED", "该视频需要登录，请配置BILIBILI_COOKIE"
                    )
                if "not available" in stderr or "not exist" in stderr:
                    raise DownloadError("VIDEO_NOT_FOUND", "视频不存在或已被删除")
                if "timeout" in stderr:
                    raise DownloadError("NETWORK_TIMEOUT", "网络超时")
                if "connection" in stderr or "network" in stderr:
                    raise DownloadError("NETWORK_ERROR", "网络连接失败")
                raise DownloadError(
                    "DOWNLOAD_FAILED", f"下载失败: {result.stderr[:200]}"
                )

            # Find downloaded file
            output_lines = result.stdout.strip().split("\n")
            for line in reversed(output_lines):
                if "Destination:" in line:
                    filepath = line.split("Destination:")[1].strip()
                    if Path(filepath).exists():
                        filepath = AudioFormatHandler.ensure_wav(filepath)
                        logger.info(f"下载完成: {filepath}")
                        return filepath

            # Fallback: find audio files matching pattern
            pattern = f"{bv_id}_P{part}*"
            audio_files = sorted(
                list(self.output_dir.glob(pattern + ".wav"))
                + list(self.output_dir.glob(pattern + ".mp3"))
                + list(self.output_dir.glob(pattern + ".m4a")),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if audio_files:
                filepath = AudioFormatHandler.ensure_wav(str(audio_files[0]))
                logger.info(f"下载完成: {filepath}")
                return filepath

            raise DownloadError("DOWNLOAD_FAILED", "下载完成但找不到输出文件")

        except subprocess.TimeoutExpired:
            raise DownloadError("NETWORK_TIMEOUT", "下载超时")
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError("DOWNLOAD_FAILED", f"下载异常: {str(e)}")
