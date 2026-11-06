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
        "摘要：\n这是摘要\n关键观点：\n- 观点一\n行动项：\n- 待办",
    )

    assert result["summary"] == "这是摘要"
    assert result["key_points"] == ["观点一"]
    assert result["action_items"] == ["待办"]


def test_parse_summary_falls_back_for_plain_text_model_output():
    result = Summarizer._normalise_result(
        Summarizer._parse_response("这是一个普通摘要"), "原始文字稿"
    )

    assert result["transcript_clean"] == "原始文字稿"
    assert result["summary"] == "这是一个普通摘要"


def test_parse_summary_accepts_json():
    result = Summarizer._parse_response(
        '{"transcript_clean":"整理","summary":"摘要"}'
    )

    assert result["summary"] == "摘要"
