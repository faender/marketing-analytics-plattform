from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from analytics.models import CampaignRecord, DataSource
from analytics.services.ingestion import IngestionError, clean_campaign_data, ingest_csv

SAMPLE_CSV = Path(__file__).resolve().parent.parent.parent / "sample_data" / "campaign_performance.csv"

MESSY_CSV = """Date, Channel , Campaign_Name,Impressions,Clicks,Cost,Conversions,Revenue
2026-01-05,Google Ads,Search - Brand,10000,500,250.00,20,1500.00
2026-01-06,Facebook Ads,Retargeting,8000,300,120.00,10,600.00
2026-01-05,Google Ads,Search - Brand,10000,500,250.00,20,1500.00
,,,,,,,
2026-01-07,Facebook Ads,Retargeting,5000,90,-40.00,3,150.00
2026-01-08,TikTok,,4000,60,30.00,1,50.00
not-a-date,Email,Newsletter,3000,80,15.00,2,90.00
2026-01-09,LinkedIn Ads,B2B Lead Gen,,,,,
"""


def test_clean_campaign_data_keeps_only_valid_unique_rows():
    df = pd.read_csv(StringIO(MESSY_CSV))

    cleaned, stats = clean_campaign_data(df)

    assert len(cleaned) == 2
    assert list(cleaned["channel"]) == ["Google Ads", "Facebook Ads"]
    assert stats["rows_total"] == 8
    assert stats["rows_dropped_empty"] == 1
    assert stats["rows_dropped_invalid"] == 4
    assert stats["rows_dropped_duplicate"] == 1


def test_clean_campaign_data_normalizes_column_names():
    df = pd.read_csv(StringIO(MESSY_CSV))

    cleaned, _ = clean_campaign_data(df)

    assert list(cleaned.columns) == [
        "date",
        "channel",
        "campaign_name",
        "impressions",
        "clicks",
        "cost",
        "conversions",
        "revenue",
    ]


def test_clean_campaign_data_missing_required_column_raises():
    df = pd.DataFrame({"date": ["2026-01-05"], "channel": ["Google Ads"]})

    with pytest.raises(IngestionError, match="Missing required columns"):
        clean_campaign_data(df)


@pytest.mark.django_db
def test_ingest_csv_creates_records_and_updates_data_source():
    data_source = DataSource.objects.create(file_name="messy.csv")

    result = ingest_csv(StringIO(MESSY_CSV), data_source)

    assert result.rows_created == 2
    assert result.rows_dropped == 6
    assert CampaignRecord.objects.filter(data_source=data_source).count() == 2

    data_source.refresh_from_db()
    assert data_source.status == DataSource.Status.PROCESSED
    assert data_source.row_count == 2


@pytest.mark.django_db
def test_ingest_csv_missing_columns_marks_data_source_failed():
    data_source = DataSource.objects.create(file_name="bad_schema.csv")
    bad_csv = StringIO("date,channel\n2026-01-05,Google Ads\n")

    with pytest.raises(IngestionError):
        ingest_csv(bad_csv, data_source)

    data_source.refresh_from_db()
    assert data_source.status == DataSource.Status.FAILED
    assert "Missing required columns" in data_source.error_message


@pytest.mark.django_db
def test_ingest_csv_against_sample_data_file():
    data_source = DataSource.objects.create(file_name="campaign_performance.csv")

    with open(SAMPLE_CSV, "rb") as f:
        result = ingest_csv(f, data_source)

    assert result.rows_total == 90
    assert result.rows_created == 84
    assert result.rows_dropped == 6
    assert CampaignRecord.objects.filter(data_source=data_source).count() == 84
