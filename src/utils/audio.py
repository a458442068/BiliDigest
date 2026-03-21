import shutil
import subprocess
from pathlib import Path

from loguru import logger

from src.exceptions import DownloadError, STTError


class AudioFormatHandler:
    SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1

    @staticmethod
    def check_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def get_audio_info(audio_path: str) -> dict:
        if not AudioFormatHandler.check_ffmpeg():
            raise DownloadError(
                "FFMPEG_NOT_AVAILABLE", "ffmpeg未安装，无法检测音频格式"
            )

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode != 0:
                raise DownloadError(
                    "FORMAT_CONVERSION_ERROR",
                    f"无法读取音频信息: {result.stderr[:200]}",
                )

            import json

            info = json.loads(result.stdout)
            stream = next(
                (s for s in info.get("streams", []) if s.get("codec_type") == "audio"),
                None,
            )
            if not stream:
                raise DownloadError("FORMAT_CONVERSION_ERROR", "未找到音频流")

            return {
                "format": Path(audio_path).suffix.lower(),
                "sample_rate": int(stream.get("sample_rate", 0)),
                "channels": int(stream.get("channels", 0)),
                "codec": stream.get("codec_name", "unknown"),
            }
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError("FORMAT_CONVERSION_ERROR", f"音频信息检测失败: {e}")

    @staticmethod
    def needs_conversion(audio_path: str) -> tuple[bool, dict]:
        info = AudioFormatHandler.get_audio_info(audio_path)
        fmt = info["format"]
        sr = info["sample_rate"]
        ch = info["channels"]

        if fmt not in AudioFormatHandler.SUPPORTED_FORMATS:
            return True, info
        if sr != AudioFormatHandler.TARGET_SAMPLE_RATE:
            return True, info
        if ch != AudioFormatHandler.TARGET_CHANNELS:
            return True, info
        return False, info

    @staticmethod
    def convert(audio_path: str, output_path: str | None = None) -> str:
        if not AudioFormatHandler.check_ffmpeg():
            raise DownloadError(
                "FFMPEG_NOT_AVAILABLE", "ffmpeg未安装，无法转换音频格式"
            )

        input_path = Path(audio_path)
        if output_path is None:
            output_path = str(input_path.with_suffix(".wav"))

        # If input and output are the same file, use a temp file first
        if Path(output_path).resolve() == input_path.resolve():
            tmp_path = str(input_path.with_suffix(".tmp.wav"))
            final_path = output_path
        else:
            tmp_path = output_path
            final_path = output_path

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            audio_path,
            "-ar",
            str(AudioFormatHandler.TARGET_SAMPLE_RATE),
            "-ac",
            str(AudioFormatHandler.TARGET_CHANNELS),
            "-acodec",
            "pcm_s16le",
            tmp_path,
        ]

        logger.info(f"转换音频: {audio_path} -> {final_path}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if result.returncode != 0:
                raise DownloadError(
                    "FORMAT_CONVERSION_ERROR", f"音频转换失败: {result.stderr[:200]}"
                )

            # Rename temp file to final path if needed
            if tmp_path != final_path:
                import os

                os.replace(tmp_path, final_path)

            logger.info(f"音频转换完成: {final_path}")
            return final_path
        except subprocess.TimeoutExpired:
            raise DownloadError("FORMAT_CONVERSION_ERROR", "音频转换超时")
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError("FORMAT_CONVERSION_ERROR", f"音频转换异常: {e}")

    @staticmethod
    def ensure_wav(audio_path: str) -> str:
        needs_conv, info = AudioFormatHandler.needs_conversion(audio_path)
        if not needs_conv:
            logger.info(f"音频格式正确，无需转换: {audio_path}")
            return audio_path

        logger.info(
            f"音频需要转换: format={info['format']}, sample_rate={info['sample_rate']}, channels={info['channels']}"
        )
        return AudioFormatHandler.convert(audio_path)
