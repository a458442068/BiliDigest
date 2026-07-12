import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from src.config import settings
from src.exceptions import DownloadError
from src.utils.audio import AudioFormatHandler
from src.utils.bv import PartInfo, validate_input, extract_video_id


METADATA_LOGIC_VERSION = 2


class BilibiliDownloader:
    BROWSER_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir).resolve() if output_dir else None

    def _resolve_output_dir(self, output_dir: str | Path | None = None) -> Path:
        if output_dir is not None:
            path = Path(output_dir).resolve()
        elif self.output_dir is not None:
            path = self.output_dir
        else:
            path = Path(settings.result_dir).resolve() / ".staging" / "downloader"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _browser_headers(self) -> list[str]:
        return [
            "--user-agent",
            self.BROWSER_USER_AGENT,
            "--add-header",
            "Referer:https://www.bilibili.com",
            "--add-header",
            "Origin:https://www.bilibili.com",
        ]

    def _write_cookie_file(self, output_dir: str | Path | None = None) -> Path | None:
        if not settings.bilibili_cookie:
            return None
        cookie_dir = self._resolve_output_dir(output_dir)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=cookie_dir,
            prefix="bilibili_cookie_",
            suffix=".txt",
            delete=False,
        ) as cookie_file:
            cookie_file.write(settings.bilibili_cookie)
            cookie_path = Path(cookie_file.name)
        os.chmod(cookie_path, 0o600)
        return cookie_path

    def _cookie_args(self, cookie_path: Path | None) -> list[str]:
        return ["--cookies", str(cookie_path)] if cookie_path else []

    def _parse_json_output(self, stdout: str) -> list[dict[str, Any]]:
        stdout = stdout.strip()
        if not stdout:
            return []
        try:
            parsed = json.loads(stdout)
            return [parsed] if isinstance(parsed, dict) else []
        except json.JSONDecodeError:
            objects = []
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    objects.append(parsed)
            return objects

    def _video_from_info(self, info: dict[str, Any]) -> dict:
        return {
            "title": info.get("fulltitle") or info.get("title", ""),
            "description": info.get("description", ""),
            "uploader": info.get("uploader", ""),
            "upload_date": info.get("upload_date", ""),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail", ""),
            "webpage_url": info.get("webpage_url", ""),
        }

    def _part_from_entry(self, entry: dict[str, Any], fallback_index: int) -> PartInfo:
        raw_part = entry.get("playlist_index") or entry.get("playlist_autonumber")
        try:
            part = int(raw_part)
        except (TypeError, ValueError):
            part = fallback_index
        raw_duration = entry.get("duration")
        try:
            duration = float(raw_duration) if raw_duration not in (None, "NA") else None
        except (TypeError, ValueError):
            duration = None
        return PartInfo(
            part=part,
            title=entry.get("title") or "",
            duration=duration,
        )

    def _parts_from_infos(self, infos: list[dict[str, Any]]) -> list[PartInfo]:
        if not infos:
            return [PartInfo(part=1, title="")]

        primary = infos[0]
        entries = primary.get("entries")
        if isinstance(entries, list) and entries:
            parts = [
                self._part_from_entry(entry, index)
                for index, entry in enumerate(entries, start=1)
                if isinstance(entry, dict)
            ]
            if parts:
                return sorted(parts, key=lambda part: part.part)

        if len(infos) > 1:
            return [
                self._part_from_entry(info, index)
                for index, info in enumerate(infos, start=1)
            ]

        try:
            duration = (
                float(primary.get("duration"))
                if primary.get("duration") not in (None, "NA")
                else None
            )
        except (TypeError, ValueError):
            duration = None
        return [
            PartInfo(
                part=1,
                title=primary.get("title") or primary.get("fulltitle") or "",
                duration=duration,
            )
        ]

    def probe_video(self, url_or_bv: str) -> dict:
        video_url = validate_input(url_or_bv)
        cmd = [
            "yt-dlp",
            "--dump-single-json",
            "--no-download",
            "--no-warnings",
            "--socket-timeout",
            "30",
        ]
        cookie_path = self._write_cookie_file()
        cmd.extend(self._cookie_args(cookie_path))
        cmd.extend(self._browser_headers())
        cmd.append(video_url)

        probe = {
            "logic_version": METADATA_LOGIC_VERSION,
            "extractor": "yt-dlp",
            "status": "ok",
            "warnings": [],
        }
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )
            if result.returncode != 0:
                warning = result.stderr[:300] or "yt-dlp metadata probe failed"
                logger.warning(f"获取视频信息失败: {warning}")
                probe["status"] = "warning"
                probe["warnings"].append(warning)
                return {
                    "video": {},
                    "parts": [PartInfo(part=1, title="")],
                    "metadata_probe": probe,
                }

            infos = self._parse_json_output(result.stdout)
            if not infos:
                warning = "yt-dlp returned no parseable metadata"
                logger.warning(f"获取视频信息异常: {warning}")
                probe["status"] = "warning"
                probe["warnings"].append(warning)
                return {
                    "video": {},
                    "parts": [PartInfo(part=1, title="")],
                    "metadata_probe": probe,
                }

            return {
                "video": self._video_from_info(infos[0]),
                "parts": self._parts_from_infos(infos),
                "metadata_probe": probe,
            }
        except Exception as e:
            logger.warning(f"获取视频信息异常: {e}")
            probe["status"] = "warning"
            probe["warnings"].append(str(e))
            return {
                "video": {},
                "parts": [PartInfo(part=1, title="")],
                "metadata_probe": probe,
            }
        finally:
            if cookie_path and cookie_path.exists():
                cookie_path.unlink()

    def get_video_info(self, url_or_bv: str) -> dict:
        return self.probe_video(url_or_bv)["video"]

    def download(
        self, url_or_bv: str, part: int = 1, output_dir: str | Path | None = None
    ) -> str:
        video_url = validate_input(url_or_bv)
        video_id = extract_video_id(url_or_bv)
        active_output_dir = self._resolve_output_dir(output_dir)
        output_template = str(active_output_dir / f"{video_id}_P{part}.%(ext)s")

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

        cookie_path = self._write_cookie_file(active_output_dir)
        if cookie_path:
            cmd.extend(["--cookies", str(cookie_path)])

        cmd.extend(self._browser_headers())
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
            pattern = f"{video_id}_P{part}*"
            audio_files = sorted(
                list(active_output_dir.glob(pattern + ".wav"))
                + list(active_output_dir.glob(pattern + ".mp3"))
                + list(active_output_dir.glob(pattern + ".m4a")),
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
        finally:
            if cookie_path and cookie_path.exists():
                cookie_path.unlink()
