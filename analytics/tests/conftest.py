import pytest
from rest_framework.test import APIClient

from analytics.models import CampaignRecord, DataSource


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_records(db):
    data_source = DataSource.objects.create(file_name="seed.csv")
    rows = [
        # date, channel, campaign, impressions, clicks, cost, conversions, revenue
        ("2026-01-01", "Google Ads", "Campaign A", 1000, 100, "50.00", 10, "500.00"),
        ("2026-01-01", "Facebook Ads", "Campaign B", 2000, 50, "25.00", 5, "100.00"),
        ("2026-01-02", "Google Ads", "Campaign A", 1500, 150, "75.00", 15, "750.00"),
        ("2026-01-08", "Google Ads", "Campaign C", 500, 20, "10.00", 1, "40.00"),
    ]
    CampaignRecord.objects.bulk_create(
        CampaignRecord(
            data_source=data_source,
            date=date,
            channel=channel,
            campaign_name=campaign,
            impressions=impressions,
            clicks=clicks,
            cost=cost,
            conversions=conversions,
            revenue=revenue,
        )
        for date, channel, campaign, impressions, clicks, cost, conversions, revenue in rows
    )
    return data_source
