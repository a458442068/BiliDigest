import pytest

from src.services.downloader import BilibiliDownloader
from src.exceptions import DownloadError


class TestBilibiliDownloader:
    def setup_method(self):
        self.downloader = BilibiliDownloader()

    def test_validate_bv_valid(self):
        url = self.downloader._validate_input("BV1xx411c7mD")
        assert "bilibili.com" in url
        assert "BV1xx411c7mD" in url

    def test_validate_bv_invalid(self):
        with pytest.raises(DownloadError) as exc_info:
            self.downloader._validate_input("INVALID_BV")
        assert exc_info.value.code == "INVALID_BV_FORMAT"

    def test_validate_url_valid(self):
        url = self.downloader._validate_input(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )
        assert url == "https://www.bilibili.com/video/BV1xx411c7mD"

    def test_validate_url_invalid(self):
        with pytest.raises(DownloadError) as exc_info:
            self.downloader._validate_input("https://youtube.com/watch?v=123")
        assert exc_info.value.code == "INVALID_URL"

    def test_validate_url_bilibili_invalid(self):
        with pytest.raises(DownloadError) as exc_info:
            self.downloader._validate_input("https://bilibili.com/invalid")
        assert exc_info.value.code == "INVALID_URL"
