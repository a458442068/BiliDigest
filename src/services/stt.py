from pathlib import Path

import httpx
import soundfile as sf
from loguru import logger

from src.config import settings
from src.exceptions import STTError
from src.utils.audio import AudioFormatHandler


class SpeechToText:
    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return

        try:
            import torch

            if torch.cuda.is_available():
                gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if gpu_mem < 4.0:
                    raise STTError(
                        "OUT_OF_MEMORY",
                        f"GPU显存不足: {gpu_mem:.1f}GB (需要至少4GB)",
                    )
                self._device = "cuda"
                logger.info(f"使用GPU推理 (显存: {gpu_mem:.1f}GB)")
            else:
                self._device = "cpu"
                logger.warning("未检测到GPU，使用CPU推理")

            from qwen_asr import Qwen3ASRModel

            model_path = settings.qwen_asr_model_path
            logger.info(f"加载模型: {model_path}")

            self._model = Qwen3ASRModel.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                device_map="auto" if self._device == "cuda" else None,
            )
            logger.info(f"模型加载完成, 设备: {self._device}")

        except STTError:
            raise
        except Exception as e:
            if "CUDA out of memory" in str(e):
                raise STTError("OUT_OF_MEMORY", f"GPU显存不足: {e}")
            raise STTError("MODEL_LOAD_ERROR", f"模型加载失败: {e}")

    def transcribe(self, audio_path: str) -> dict:
        backend = settings.stt_backend

        if backend == "remote":
            logger.info("STT后端: 远程")
            return self._transcribe_remote(audio_path)
        elif backend == "local":
            logger.info("STT后端: 本地")
            return self._transcribe_local(audio_path)
        else:  # "default"
            logger.info("STT后端: 默认 (本地优先)")
            try:
                return self._transcribe_local(audio_path)
            except Exception as local_err:
                logger.warning(f"本地STT失败: {local_err}")
                try:
                    result = self._transcribe_remote(audio_path)
                    logger.info("远程STT fallback成功")
                    return result
                except Exception as remote_err:
                    logger.error(f"远程STT也失败: {remote_err}")
                    raise STTError(
                        "ALL_BACKENDS_FAILED",
                        f"本地STT失败: {local_err}; 远程STT失败: {remote_err}",
                    )

    def _transcribe_local(self, audio_path: str) -> dict:
        self._load_model()

        try:
            audio_path = AudioFormatHandler.ensure_wav(audio_path)
        except Exception:
            logger.warning("音频格式转换失败，尝试直接读取")

        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise STTError("INFERENCE_ERROR", f"音频文件不存在: {audio_path}")

        try:
            audio_array, sample_rate = sf.read(str(audio_file))
            duration_seconds = len(audio_array) / sample_rate

            logger.info(
                f"本地STT: {audio_path} (采样率: {sample_rate}Hz, 时长: {duration_seconds:.1f}s)"
            )

            chunk_duration = settings.stt_chunk_duration
            if chunk_duration > 0 and duration_seconds > chunk_duration:
                return self._transcribe_chunked(
                    audio_array, sample_rate, duration_seconds, chunk_duration
                )

            results = self._model.transcribe(audio_path)
            if not results:
                raise STTError("INFERENCE_ERROR", "语音识别返回空结果")
            transcription = results[0]
            transcript = (
                transcription.text
                if hasattr(transcription, "text")
                else str(transcription)
            )

            language = (
                transcription.language
                if hasattr(transcription, "language") and transcription.language
                else "unknown"
            )

            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"本地STT完成, 语言: {language}")
            return {
                "transcript": transcript,
                "language": language,
                "duration_seconds": duration_seconds,
            }

        except STTError:
            raise
        except Exception as e:
            if "CUDA out of memory" in str(e):
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                raise STTError("OUT_OF_MEMORY", f"推理时GPU显存不足: {e}")
            raise STTError("INFERENCE_ERROR", f"推理异常: {e}")

    def _transcribe_chunked(
        self,
        audio_array,
        sample_rate: int,
        duration_seconds: float,
        chunk_duration: int,
    ) -> dict:
        import torch
        from qwen_asr.inference.utils import split_audio_into_chunks

        chunks = split_audio_into_chunks(
            audio_array, sample_rate, max_chunk_sec=chunk_duration
        )
        logger.info(f"音频分为 {len(chunks)} 块, 每块最大 {chunk_duration}s")

        transcripts = []
        detected_language = None

        for i, (chunk_wav, offset_sec) in enumerate(chunks):
            logger.info(
                f"处理第 {i + 1}/{len(chunks)} 块 (offset: {offset_sec:.1f}s, "
                f"时长: {len(chunk_wav) / sample_rate:.1f}s)"
            )
            results = self._model.transcribe((chunk_wav, sample_rate))
            if not results:
                logger.warning(f"第 {i + 1} 块返回空结果，跳过")
                continue

            transcription = results[0]
            text = (
                transcription.text
                if hasattr(transcription, "text")
                else str(transcription)
            )
            if text.strip():
                transcripts.append(text)

            if detected_language is None:
                if hasattr(transcription, "language") and transcription.language:
                    detected_language = transcription.language

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        if not detected_language:
            detected_language = "unknown"

        logger.info(f"分块STT完成, 共 {len(chunks)} 块, 语言: {detected_language}")
        return {
            "transcript": " ".join(transcripts),
            "language": detected_language,
            "duration_seconds": duration_seconds,
        }

    def _transcribe_remote(self, audio_path: str) -> dict:
        if not settings.stt_api_url:
            raise STTError("REMOTE_CONFIG_ERROR", "STT_API_URL 未配置")

        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise STTError("INFERENCE_ERROR", f"音频文件不存在: {audio_path}")

        url = f"{settings.stt_api_url.rstrip('/')}/v1/audio/transcriptions"
        headers = {}
        if settings.stt_api_key:
            headers["Authorization"] = f"Bearer {settings.stt_api_key}"

        logger.info(f"远程STT: {url}")

        try:
            with open(audio_path, "rb") as f:
                files = {"file": (audio_file.name, f, "audio/wav")}
                data = {"response_format": "verbose_json"}
                response = httpx.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=600,
                )

            if response.status_code != 200:
                raise STTError(
                    "REMOTE_API_ERROR",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )

            result = response.json()
            logger.info("远程STT完成")
            return {
                "transcript": result.get("text", ""),
                "language": result.get("language", "en"),
                "duration_seconds": result.get("duration"),
            }

        except STTError:
            raise
        except httpx.TimeoutException:
            raise STTError("REMOTE_TIMEOUT", "远程STT调用超时")
        except Exception as e:
            raise STTError("REMOTE_ERROR", f"远程STT调用异常: {e}")

    def release(self):
        if self._model is not None:
            del self._model
            self._model = None
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("模型已释放")
