import pytest

from src.services.stt import SpeechToText
from src.exceptions import STTError


class TestSpeechToText:
    def setup_method(self):
        self.stt = SpeechToText()

    def test_detect_language_chinese(self):
        text = "这是一个中文测试句子"
        assert self.stt._detect_language(text) == "zh"

    def test_detect_language_english(self):
        text = "This is an English test sentence"
        assert self.stt._detect_language(text) == "en"

    def test_detect_language_mixed(self):
        text = "Hello 你好 World 世界"
        assert self.stt._detect_language(text) == "zh"

    def test_transcribe_nonexistent_file(self):
        with pytest.raises(STTError) as exc_info:
            self.stt.transcribe("/nonexistent/audio.wav")
        assert exc_info.value.code == "INFERENCE_ERROR"
