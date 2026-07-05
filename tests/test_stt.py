import pytest

from src.services.stt import SpeechToText
from src.exceptions import STTError


class TestSpeechToText:
    def setup_method(self):
        self.stt = SpeechToText()

    def test_transcribe_nonexistent_file(self, monkeypatch):
        monkeypatch.setattr("src.services.stt.settings.stt_backend", "local")
        with pytest.raises(STTError) as exc_info:
            self.stt.transcribe("/nonexistent/audio.wav")
        assert exc_info.value.code == "INFERENCE_ERROR"
