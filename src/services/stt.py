from pathlib import Path

import soundfile as sf
from loguru import logger

from src.config import settings
from src.exceptions import STTError
from src.utils.audio import AudioFormatHandler


class SpeechToText:
    def __init__(self):
        self._model = None
        self._processor = None
        self._device = None

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

            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            model_path = settings.qwen_asr_model_path
            logger.info(f"加载模型: {model_path}")

            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                low_cpu_mem_usage=True,
            ).to(self._device)

            self._processor = AutoProcessor.from_pretrained(model_path)
            logger.info("模型加载完成")

        except STTError:
            raise
        except Exception as e:
            if "CUDA out of memory" in str(e):
                raise STTError("OUT_OF_MEMORY", f"GPU显存不足: {e}")
            raise STTError("MODEL_LOAD_ERROR", f"模型加载失败: {e}")

    def transcribe(self, audio_path: str) -> dict:
        self._load_model()

        # Ensure correct format (fallback conversion)
        try:
            audio_path = AudioFormatHandler.ensure_wav(audio_path)
        except Exception:
            logger.warning("音频格式转换失败，尝试直接读取")

        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise STTError("INFERENCE_ERROR", f"音频文件不存在: {audio_path}")

        try:
            import torch

            # Read audio
            audio_array, sample_rate = sf.read(str(audio_file))
            logger.info(f"音频采样率: {sample_rate}Hz")

            # Resample to 16kHz if needed
            if sample_rate != 16000:
                import torch.nn.functional as F

                audio_tensor = torch.tensor(audio_array, dtype=torch.float32)
                if audio_tensor.dim() > 1:
                    audio_tensor = audio_tensor.mean(dim=1)
                audio_tensor = audio_tensor.unsqueeze(0).unsqueeze(0)
                audio_tensor = F.interpolate(
                    audio_tensor,
                    size=len(audio_array) * 16000 // sample_rate,
                    mode="linear",
                    align_corners=False,
                )
                audio_array = audio_tensor.squeeze().numpy()
                sample_rate = 16000
                logger.info("已重采样到16kHz")

            # Prepare inputs
            inputs = self._processor(
                audio_array,
                sampling_rate=sample_rate,
                return_tensors="pt",
            ).to(self._device)

            # Run inference
            with torch.no_grad():
                outputs = self._model.generate(**inputs, max_new_tokens=256)

            transcript = self._processor.batch_decode(
                outputs, skip_special_tokens=True
            )[0]

            # Detect language
            language = self._detect_language(transcript)

            # Calculate duration
            duration_seconds = len(audio_array) / sample_rate

            # Clear GPU cache
            if self._device == "cuda":
                torch.cuda.empty_cache()

            return {
                "transcript": transcript,
                "language": language,
                "duration_seconds": duration_seconds,
            }

        except STTError:
            raise
        except Exception as e:
            if "CUDA out of memory" in str(e):
                if self._device == "cuda":
                    import torch

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
            del self._processor
            self._model = None
            self._processor = None
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("模型已释放")
