from src.utils.subtitle import (
    format_srt_time,
    format_vtt_time,
    merge_segments_to_sentences,
    segments_to_srt,
    segments_to_vtt,
    transcript_to_srt,
    transcript_to_vtt,
)


class TestSubtitleUtils:
    def test_format_srt_time(self):
        assert format_srt_time(0) == "00:00:00,000"
        assert format_srt_time(61.5) == "00:01:01,500"
        assert format_srt_time(3661.123) == "01:01:01,123"

    def test_format_vtt_time(self):
        assert format_vtt_time(0) == "00:00:00.000"
        assert format_vtt_time(61.5) == "00:01:01.500"

    def test_merge_segments_basic(self):
        segments = [
            {"text": "Hello ", "start": 0.0, "end": 0.5},
            {"text": "world.", "start": 0.5, "end": 1.0},
            {"text": "How ", "start": 1.0, "end": 1.5},
            {"text": "are ", "start": 1.5, "end": 2.0},
            {"text": "you?", "start": 2.0, "end": 2.5},
        ]
        result = merge_segments_to_sentences(segments)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world."
        assert result[1]["text"] == "How are you?"

    def test_merge_segments_gap(self):
        segments = [
            {"text": "First ", "start": 0.0, "end": 0.5},
            {"text": "part", "start": 0.5, "end": 1.0},
            {"text": "Second", "start": 2.0, "end": 2.5},  # gap > 0.3s
        ]
        result = merge_segments_to_sentences(segments, gap_threshold=0.3)
        assert len(result) == 2

    def test_segments_to_srt(self):
        segments = [
            {"text": "Hello ", "start": 0.0, "end": 0.5},
            {"text": "world.", "start": 0.5, "end": 1.0},
        ]
        srt = segments_to_srt(segments)
        assert "00:00:00,000 --> 00:00:01,000" in srt
        assert "Hello world." in srt
        assert srt.startswith("1\n")

    def test_segments_to_vtt(self):
        segments = [
            {"text": "Hello ", "start": 0.0, "end": 0.5},
            {"text": "world.", "start": 0.5, "end": 1.0},
        ]
        vtt = segments_to_vtt(segments)
        assert vtt.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:01.000" in vtt
        assert "Hello world." in vtt

    def test_transcript_to_srt_fallback(self):
        srt = transcript_to_srt("Line one\nLine two", 10.0)
        assert "00:00:00,000 --> 00:00:05,000" in srt
        assert "Line one" in srt
        assert "Line two" in srt

    def test_transcript_to_vtt_fallback(self):
        vtt = transcript_to_vtt("Line one\nLine two", 10.0)
        assert vtt.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:05.000" in vtt

    def test_empty_segments(self):
        assert segments_to_srt([]) == ""
        assert segments_to_vtt([]) == ""
