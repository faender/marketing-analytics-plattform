from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from analytics.services.ai_agent import MAX_TOOL_ITERATIONS, AIAgentError, answer_question


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(block_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def _response(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


@pytest.fixture(autouse=True)
def anthropic_api_key(settings):
    settings.ANTHROPIC_API_KEY = "test-key"


@pytest.mark.django_db
@patch("analytics.services.ai_agent.anthropic.Anthropic")
def test_answer_question_uses_tool_and_returns_final_answer(mock_anthropic, seeded_records):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _response(
            "tool_use",
            [_tool_use_block("tu_1", "get_summary", {"channel": "Google Ads"})],
        ),
        _response("end_turn", [_text_block("Google Ads generated $1290.00 in revenue.")]),
    ]
    mock_anthropic.return_value = mock_client

    result = answer_question("How much revenue did Google Ads generate?")

    assert result["answer"] == "Google Ads generated $1290.00 in revenue."
    assert result["tool_calls"] == [{"tool": "get_summary", "input": {"channel": "Google Ads"}}]
    assert mock_client.messages.create.call_count == 2


@pytest.mark.django_db
@patch("analytics.services.ai_agent.anthropic.Anthropic")
def test_answer_question_without_tool_call_returns_text_directly(mock_anthropic):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _response("end_turn", [_text_block("No data has been uploaded yet.")]),
    ]
    mock_anthropic.return_value = mock_client

    result = answer_question("What's the total revenue?")

    assert result["answer"] == "No data has been uploaded yet."
    assert result["tool_calls"] == []
    assert mock_client.messages.create.call_count == 1


def test_answer_question_raises_without_api_key(settings):
    settings.ANTHROPIC_API_KEY = ""

    with pytest.raises(AIAgentError, match="not configured"):
        answer_question("What's the total revenue?")


@pytest.mark.django_db
@patch("analytics.services.ai_agent.anthropic.Anthropic")
def test_answer_question_stops_after_max_iterations(mock_anthropic):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _response("tool_use", [_tool_use_block(f"tu_{i}", "get_summary", {})])
        for i in range(MAX_TOOL_ITERATIONS)
    ]
    mock_anthropic.return_value = mock_client

    result = answer_question("Keep digging forever")

    assert "wasn't able to fully answer" in result["answer"]
    assert len(result["tool_calls"]) == MAX_TOOL_ITERATIONS
    assert mock_client.messages.create.call_count == MAX_TOOL_ITERATIONS


@pytest.mark.django_db
@patch("analytics.services.ai_agent.anthropic.Anthropic")
def test_answer_question_wraps_api_errors(mock_anthropic):
    fake_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=fake_request)
    mock_anthropic.return_value = mock_client

    with pytest.raises(AIAgentError, match="Anthropic API error"):
        answer_question("What's the total revenue?")


@pytest.mark.django_db
@patch("analytics.services.ai_agent.anthropic.Anthropic")
def test_answer_question_handles_unknown_tool_gracefully(mock_anthropic):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _response("tool_use", [_tool_use_block("tu_1", "delete_everything", {})]),
        _response("end_turn", [_text_block("I can't do that, but here's what I can tell you.")]),
    ]
    mock_anthropic.return_value = mock_client

    result = answer_question("Delete all the data")

    assert result["answer"] == "I can't do that, but here's what I can tell you."
    assert result["tool_calls"] == [{"tool": "delete_everything", "input": {}}]
