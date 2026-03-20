import re
import subprocess
from pathlib import Path

from loguru import logger

from src.config import settings
from src.exceptions import DownloadError
from src.utils.audio import AudioFormatHandler


class BilibiliDownloader:
    BV_PATTERN = re.compile(r"^BV[1-9A-HJ-NP-Za-km-z]{10}$")
    URL_PATTERN = re.compile(
        r"https?://(www\.)?bilibili\.com/video/BV[1-9A-HJ-NP-Za-km-z]{10}"
    )

    def __init__(self, output_dir: str = "/tmp/stt_server"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _validate_input(self, url_or_bv: str) -> str:
        if self.BV_PATTERN.match(url_or_bv):
            return f"https://www.bilibili.com/video/{url_or_bv}"
        if self.URL_PATTERN.match(url_or_bv):
            return url_or_bv
        if "bilibili.com" in url_or_bv:
            raise DownloadError("INVALID_URL", f"无效的B站URL: {url_or_bv}")
        raise DownloadError("INVALID_BV_FORMAT", f"无效的BV号: {url_or_bv}")

    def download(self, url_or_bv: str) -> str:
        video_url = self._validate_input(url_or_bv)
        output_template = str(self.output_dir / "%(id)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format",
            "wav",
            "--audio-quality",
            "0",
            "-o",
            output_template,
            "--no-playlist",
            "--socket-timeout",
            "30",
        ]

        if settings.bilibili_cookie:
            cookie_file = self.output_dir / "cookie.txt"
            cookie_file.write_text(settings.bilibili_cookie)
            cmd.extend(["--cookies", str(cookie_file)])

        cmd.append(video_url)

        logger.info(f"开始下载: {video_url}")
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

            # Fallback: find audio files
            audio_files = sorted(
                list(self.output_dir.glob("*.wav"))
                + list(self.output_dir.glob("*.mp3"))
                + list(self.output_dir.glob("*.m4a")),
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
