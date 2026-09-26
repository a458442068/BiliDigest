import pytest

from src.services.summarizer import Summarizer


def test_parse_structured_summary_json():
    result = Summarizer._parse_response(
        '{"transcript_clean":"整理稿","summary":"摘要",'
        '"key_points":["观点"],"chapters":[],"action_items":["待办"],"entities":[]}'
    )

    assert result["transcript_clean"] == "整理稿"
    assert result["key_points"] == ["观点"]


def test_parse_summary_rejects_unstructured_model_output():
    with pytest.raises(ValueError):
        Summarizer._parse_response("这不是约定格式")
