import pytest

from src.services.summarizer import Summarizer


def test_parse_structured_summary_json():
    result = Summarizer._parse_response(
        '{"transcript_clean":"整理稿","summary":"摘要",'
        '"key_points":["观点"],"chapters":[],"action_items":["待办"],"entities":[]}'
    )

    assert result["transcript_clean"] == "整理稿"
    assert result["key_points"] == ["观点"]


def test_parse_summary_accepts_small_model_section_format():
    result = Summarizer._parse_response(
        "[整理稿]\n这是整理稿\n[摘要]\n这是摘要\n[关键观点]\n- 观点一\n"
        "[章节]\n- 开场\n[行动项]\n- 待办\n[实体]\n- BiliDigest",
    )

    assert result["transcript_clean"] == "这是整理稿"
    assert result["summary"] == "这是摘要"
    assert result["key_points"] == ["观点一"]
    assert result["chapters"] == [{"title": "开场", "summary": ""}]


def test_parse_summary_falls_back_for_plain_text_model_output():
    result = Summarizer._parse_response("这是一个普通摘要", source_text="原始文字稿")

    assert result["transcript_clean"] == "原始文字稿"
    assert result["summary"] == "这是一个普通摘要"


def test_parse_summary_accepts_json_surrounded_by_prose():
    result = Summarizer._parse_response(
        "好的，结果如下：\n```json\n{\"transcript_clean\":\"整理\",\"summary\":\"摘要\"}\n```"
    )

    assert result["summary"] == "摘要"
