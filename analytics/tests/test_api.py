from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from analytics.models import CampaignRecord
from analytics.services.ai_agent import AIAgentError

VALID_CSV = (
    b"date,channel,campaign_name,impressions,clicks,cost,conversions,revenue\n"
    b"2026-01-01,Google Ads,Campaign A,1000,100,50.00,10,500.00\n"
    b"2026-01-02,Facebook Ads,Campaign B,2000,50,25.00,5,100.00\n"
)
MISSING_COLUMNS_CSV = b"date,channel\n2026-01-01,Google Ads\n"


@pytest.mark.django_db
def test_upload_valid_csv_creates_datasource_and_records(api_client):
    upload = SimpleUploadedFile("campaigns.csv", VALID_CSV, content_type="text/csv")

    response = api_client.post("/api/upload/", {"file": upload}, format="multipart")

    assert response.status_code == 201
    assert response.data["status"] == "processed"
    assert response.data["row_count"] == 2
    assert CampaignRecord.objects.count() == 2


@pytest.mark.django_db
def test_upload_missing_columns_returns_400_and_marks_failed(api_client):
    upload = SimpleUploadedFile("bad.csv", MISSING_COLUMNS_CSV, content_type="text/csv")

    response = api_client.post("/api/upload/", {"file": upload}, format="multipart")

    assert response.status_code == 400
    assert response.data["status"] == "failed"
    assert "Missing required columns" in response.data["error_message"]
    assert CampaignRecord.objects.count() == 0


@pytest.mark.django_db
def test_upload_rejects_non_csv_extension(api_client):
    upload = SimpleUploadedFile("notes.txt", b"hello world", content_type="text/plain")

    response = api_client.post("/api/upload/", {"file": upload}, format="multipart")

    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_requires_file(api_client):
    response = api_client.post("/api/upload/", {}, format="multipart")

    assert response.status_code == 400


@pytest.mark.django_db
def test_datasource_list_returns_uploads(api_client, seeded_records):
    response = api_client.get("/api/datasources/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["file_name"] == "seed.csv"


@pytest.mark.django_db
def test_metrics_summary_endpoint_returns_totals(api_client, seeded_records):
    response = api_client.get("/api/metrics/summary/")

    assert response.status_code == 200
    assert response.data["totals"]["revenue"] == 1390.0
    assert response.data["averages"]["cpc"] == pytest.approx(0.5)


@pytest.mark.django_db
def test_metrics_summary_channel_filter(api_client, seeded_records):
    response = api_client.get("/api/metrics/summary/", {"channel": "Google Ads"})

    assert response.status_code == 200
    assert response.data["totals"]["impressions"] == 3000


@pytest.mark.django_db
def test_metrics_summary_invalid_date_returns_400(api_client):
    response = api_client.get("/api/metrics/summary/", {"date_from": "not-a-date"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_metrics_trends_endpoint(api_client, seeded_records):
    response = api_client.get(
        "/api/metrics/trends/",
        {"granularity": "day", "metric": "revenue", "date_to": "2026-01-02"},
    )

    assert response.status_code == 200
    assert response.data["trends"] == [
        {"period": "2026-01-01", "value": 600.0},
        {"period": "2026-01-02", "value": 750.0},
    ]


@pytest.mark.django_db
def test_metrics_trends_invalid_metric_returns_400(api_client, seeded_records):
    response = api_client.get("/api/metrics/trends/", {"metric": "bogus"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_top_campaigns_endpoint(api_client, seeded_records):
    response = api_client.get(
        "/api/metrics/top-campaigns/", {"metric": "revenue", "limit": 2}
    )

    assert response.status_code == 200
    names = [c["campaign_name"] for c in response.data["top_campaigns"]]
    assert names == ["Campaign A", "Campaign B"]


@pytest.mark.django_db
def test_dashboard_page_loads(api_client):
    response = api_client.get("/")

    assert response.status_code == 200


@pytest.mark.django_db
@patch("analytics.views.answer_question")
def test_ask_endpoint_returns_agent_answer(mock_answer_question, api_client):
    mock_answer_question.return_value = {
        "answer": "Total revenue was $1,390.00.",
        "tool_calls": [{"tool": "get_summary", "input": {}}],
    }

    response = api_client.post("/api/ask/", {"question": "What's total revenue?"}, format="json")

    assert response.status_code == 200
    assert response.data["answer"] == "Total revenue was $1,390.00."
    mock_answer_question.assert_called_once_with("What's total revenue?")


@pytest.mark.django_db
def test_ask_endpoint_requires_question(api_client):
    response = api_client.post("/api/ask/", {}, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
@patch("analytics.views.answer_question")
def test_ask_endpoint_returns_502_on_agent_error(mock_answer_question, api_client):
    mock_answer_question.side_effect = AIAgentError("ANTHROPIC_API_KEY is not configured.")

    response = api_client.post("/api/ask/", {"question": "What's total revenue?"}, format="json")

    assert response.status_code == 502
    assert "not configured" in response.data["detail"]
