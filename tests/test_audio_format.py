import shutil
import pytest
from pathlib import Path
from unittest.mock import patch

from src.utils.audio import AudioFormatHandler
from src.exceptions import DownloadError


class TestAudioFormatHandler:
    def test_check_ffmpeg(self):
        result = AudioFormatHandler.check_ffmpeg()
        assert isinstance(result, bool)

    def test_needs_conversion_nonexistent(self):
        with pytest.raises(DownloadError):
            AudioFormatHandler.needs_conversion("/nonexistent/audio.wav")

    @patch("shutil.which", return_value=None)
    def test_check_ffmpeg_not_available(self, mock_which):
        assert AudioFormatHandler.check_ffmpeg() is False

    @patch("shutil.which", return_value=None)
    def test_convert_no_ffmpeg(self, mock_which):
        with pytest.raises(DownloadError) as exc_info:
            AudioFormatHandler.convert("/some/audio.mp3")
        assert exc_info.value.code == "FFMPEG_NOT_AVAILABLE"

    @patch("shutil.which", return_value=None)
    def test_get_audio_info_no_ffmpeg(self, mock_which):
        with pytest.raises(DownloadError) as exc_info:
            AudioFormatHandler.get_audio_info("/some/audio.wav")
        assert exc_info.value.code == "FFMPEG_NOT_AVAILABLE"
