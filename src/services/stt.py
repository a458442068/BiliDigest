from pathlib import Path

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
        self._load_model()

        # Ensure correct format
        try:
            audio_path = AudioFormatHandler.ensure_wav(audio_path)
        except Exception:
            logger.warning("音频格式转换失败，尝试直接读取")

        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise STTError("INFERENCE_ERROR", f"音频文件不存在: {audio_path}")

        try:
            # Get audio duration
            audio_array, sample_rate = sf.read(str(audio_file))
            duration_seconds = len(audio_array) / sample_rate

            logger.info(
                f"开始语音识别: {audio_path} (采样率: {sample_rate}Hz, 时长: {duration_seconds:.1f}s)"
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
                else self._detect_language(transcript)
            )

            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"语音识别完成, 语言: {language}")
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

    def _detect_language(self, text: str) -> str:
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        if chinese_chars > len(text) * 0.3:
            return "zh"
        return "en"

    def release(self):
        if self._model is not None:
            del self._model
            self._model = None
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("模型已释放")
