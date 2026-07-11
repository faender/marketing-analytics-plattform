import json

import anthropic
from django.conf import settings

from analytics.services import metrics as metrics_service
from analytics.services.metrics import GRANULARITY_FREQ, METRIC_COLUMNS

MAX_TOOL_ITERATIONS = 5

TOOLS = [
    {
        "name": "get_summary",
        "description": (
            "Get total impressions, clicks, cost, conversions, revenue, and derived "
            "rates (CTR, CPC, CPA, ROAS) for the campaign data, optionally filtered by "
            "date range and/or channel. Use this for questions about totals, averages, "
            "or overall performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "Inclusive start date, format YYYY-MM-DD.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Inclusive end date, format YYYY-MM-DD.",
                },
                "channel": {
                    "type": "string",
                    "description": "Restrict to a single channel, e.g. 'Google Ads'.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_trends",
        "description": (
            "Get a time series of one metric summed per day/week/month. Use this for "
            "questions about how a metric changed over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "granularity": {"type": "string", "enum": list(GRANULARITY_FREQ)},
                "metric": {"type": "string", "enum": METRIC_COLUMNS},
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                "channel": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_top_campaigns",
        "description": (
            "Get the top N campaigns ranked by one metric, optionally filtered by date "
            "range and/or channel. Use this for 'best/worst campaign' style questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": METRIC_COLUMNS},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                "channel": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
]

TOOL_FUNCTIONS = {
    "get_summary": metrics_service.get_summary,
    "get_trends": metrics_service.get_trends,
    "get_top_campaigns": metrics_service.get_top_campaigns,
}


class AIAgentError(Exception):
    """Raised when the AI agent can't be reached or isn't configured."""


def _execute_tool(name: str, tool_input: dict) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        return func(**tool_input)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}


def _build_system_prompt() -> str:
    channels = metrics_service.get_available_channels()
    date_range = metrics_service.get_date_range()
    return (
        "You are a marketing analytics assistant. Answer the user's question about "
        "campaign performance data using ONLY numbers returned by the tools below - "
        "never invent, estimate, or recall numbers from outside a tool result. If the "
        "tools return no data for the question asked, say so plainly.\n\n"
        f"Available channels: {', '.join(channels) if channels else '(none uploaded yet)'}\n"
        f"Data date range: {date_range['min_date'] or 'n/a'} to {date_range['max_date'] or 'n/a'}\n"
        f"Available metrics: {', '.join(METRIC_COLUMNS)}\n\n"
        "Keep answers concise (2-4 sentences), lead with the number(s) the user asked "
        "for, and mention which channel/campaign/date range they refer to."
    )


def answer_question(question: str) -> dict:
    """Answer a natural-language question about the campaign data.

    Runs a manual tool-use loop: Claude can call get_summary/get_trends/
    get_top_campaigns (the same functions the dashboard API uses) to fetch
    real numbers before answering, rather than being handed a data dump.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIAgentError("ANTHROPIC_API_KEY is not configured.")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    system = _build_system_prompt()
    messages = [{"role": "user", "content": question}]
    tool_calls_made = []

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=1024,
                system=system,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                answer_text = next(
                    (block.text for block in response.content if block.type == "text"), ""
                )
                return {"answer": answer_text, "tool_calls": tool_calls_made}

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = _execute_tool(block.name, block.input)
                tool_calls_made.append({"tool": block.name, "input": block.input})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
    except anthropic.APIError as exc:
        raise AIAgentError(f"Anthropic API error: {exc}") from exc

    return {
        "answer": (
            "I wasn't able to fully answer that within the allotted number of tool "
            "calls. Try asking a more specific question."
        ),
        "tool_calls": tool_calls_made,
    }
