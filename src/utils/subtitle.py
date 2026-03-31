def format_srt_time(seconds: float) -> str:
    """将秒数转为 SRT 时间格式 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """将秒数转为 VTT 时间格式 HH:MM:SS.mmm"""
    return format_srt_time(seconds).replace(",", ".")


def merge_segments_to_sentences(
    segments: list[dict], gap_threshold: float = 0.3
) -> list[dict]:
    """将词级时间戳合并为句级。

    合并规则：遇到句末标点（.!?。！？）或停顿 > gap_threshold 时切分。
    """
    if not segments:
        return []

    sentence_end_chars = set(".!?。！？…")
    sentences = []
    current_text = ""
    current_start = segments[0]["start"]
    current_end = segments[0]["end"]

    for i, seg in enumerate(segments):
        text = seg["text"]
        if not text.strip():
            continue

        # 检查是否需要切分：停顿过长
        if i > 0 and seg["start"] - current_end > gap_threshold:
            if current_text.strip():
                sentences.append({
                    "text": current_text.strip(),
                    "start": current_start,
                    "end": current_end,
                })
            current_text = text
            current_start = seg["start"]
            current_end = seg["end"]
            continue

        current_text += text
        current_end = seg["end"]

        # 检查句末标点
        if text[-1] in sentence_end_chars:
            if current_text.strip():
                sentences.append(
                    {
                        "text": current_text.strip(),
                        "start": current_start,
                        "end": current_end,
                    }
                )
            current_text = ""
            if i + 1 < len(segments):
                current_start = segments[i + 1]["start"]

    # 收尾
    if current_text.strip():
        sentences.append(
            {
                "text": current_text.strip(),
                "start": current_start,
                "end": current_end,
            }
        )

    return sentences


def segments_to_srt(segments: list[dict]) -> str:
    """将时间戳片段转为 SRT 格式字符串。"""
    sentences = merge_segments_to_sentences(segments)
    if not sentences:
        return ""

    lines = []
    for i, sent in enumerate(sentences, 1):
        lines.append(str(i))
        lines.append(
            f"{format_srt_time(sent['start'])} --> {format_srt_time(sent['end'])}"
        )
        lines.append(sent["text"])
        lines.append("")

    return "\n".join(lines)


def segments_to_vtt(segments: list[dict]) -> str:
    """将时间戳片段转为 VTT 格式字符串。"""
    sentences = merge_segments_to_sentences(segments)
    if not sentences:
        return ""

    lines = ["WEBVTT", ""]
    for i, sent in enumerate(sentences, 1):
        lines.append(str(i))
        lines.append(
            f"{format_vtt_time(sent['start'])} --> {format_vtt_time(sent['end'])}"
        )
        lines.append(sent["text"])
        lines.append("")

    return "\n".join(lines)


def transcript_to_srt(transcript: str, duration: float) -> str:
    """无时间戳时，将纯文本均匀分布为 SRT（fallback）。"""
    lines = [l.strip() for l in transcript.split("\n") if l.strip()]
    if not lines:
        return ""

    seg_duration = duration / len(lines)
    result = []
    for i, line in enumerate(lines):
        start = i * seg_duration
        end = (i + 1) * seg_duration
        result.append(str(i + 1))
        result.append(f"{format_srt_time(start)} --> {format_srt_time(end)}")
        result.append(line)
        result.append("")

    return "\n".join(result)


def transcript_to_vtt(transcript: str, duration: float) -> str:
    """无时间戳时，将纯文本均匀分布为 VTT（fallback）。"""
    srt = transcript_to_srt(transcript, duration)
    if not srt:
        return ""
    return "WEBVTT\n\n" + srt.replace(",", ".")
