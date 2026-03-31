import pytest

from src.services.downloader import BilibiliDownloader
from src.utils.bv import validate_input, extract_video_id, _is_supported_url
from src.exceptions import DownloadError


class TestBilibiliDownloader:
    def setup_method(self):
        self.downloader = BilibiliDownloader()

    def test_validate_bv_valid(self):
        url = validate_input("BV1xx411c7mD")
        assert "bilibili.com" in url
        assert "BV1xx411c7mD" in url

    def test_validate_bv_invalid(self):
        with pytest.raises(DownloadError) as exc_info:
            validate_input("INVALID_BV")
        assert exc_info.value.code == "INVALID_URL"

    def test_validate_url_valid(self):
        url = validate_input("https://www.bilibili.com/video/BV1xx411c7mD")
        assert url == "https://www.bilibili.com/video/BV1xx411c7mD"

    def test_validate_url_with_query_params(self):
        url = validate_input("https://www.bilibili.com/video/BV1xx411c7mD?spm_id_from=333.1")
        assert url == "https://www.bilibili.com/video/BV1xx411c7mD"

    def test_validate_url_unsupported(self):
        with pytest.raises(DownloadError) as exc_info:
            validate_input("https://example.com/video/123")
        assert exc_info.value.code == "INVALID_URL"

    def test_validate_youtube_url(self):
        url = validate_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "youtube.com" in url

    def test_extract_video_id_from_url(self):
        vid = extract_video_id("https://www.bilibili.com/video/BV1xx411c7mD")
        assert vid == "BV1xx411c7mD"

    def test_extract_video_id_direct(self):
        vid = extract_video_id("BV1xx411c7mD")
        assert vid == "BV1xx411c7mD"

    def test_extract_video_id_youtube(self):
        vid = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert len(vid) == 12  # hash-based ID

    def test_is_supported_url(self):
        assert _is_supported_url("https://www.bilibili.com/video/BV1xx411c7mD")
        assert _is_supported_url("https://www.youtube.com/watch?v=test")
        assert _is_supported_url("https://x.com/user/status/123")
        assert _is_supported_url("https://soundcloud.com/artist/track")
        assert not _is_supported_url("https://example.com/video")
