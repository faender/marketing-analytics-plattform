import pytest

from analytics.services.metrics import (
    get_available_channels,
    get_date_range,
    get_summary,
    get_top_campaigns,
    get_trends,
)

# seeded_records fixture lives in conftest.py (shared with test_api.py)


@pytest.mark.django_db
def test_get_summary_totals_and_averages(seeded_records):
    summary = get_summary()

    assert summary["row_count"] == 4
    assert summary["totals"] == {
        "impressions": 5000,
        "clicks": 320,
        "cost": 160.0,
        "conversions": 31,
        "revenue": 1390.0,
    }
    assert summary["averages"]["ctr"] == pytest.approx(0.064)
    assert summary["averages"]["cpc"] == pytest.approx(0.5)
    assert summary["averages"]["cpa"] == pytest.approx(round(160 / 31, 4))
    assert summary["averages"]["roas"] == pytest.approx(round(1390 / 160, 4))


@pytest.mark.django_db
def test_get_summary_filters_by_channel(seeded_records):
    summary = get_summary(channel="Google Ads")

    assert summary["totals"] == {
        "impressions": 3000,
        "clicks": 270,
        "cost": 135.0,
        "conversions": 26,
        "revenue": 1290.0,
    }
    assert summary["averages"]["ctr"] == pytest.approx(0.09)


@pytest.mark.django_db
def test_get_summary_with_no_data_returns_zeroed_structure():
    summary = get_summary()

    assert summary["row_count"] == 0
    assert summary["totals"] == {
        "impressions": 0,
        "clicks": 0,
        "cost": 0.0,
        "conversions": 0,
        "revenue": 0.0,
    }
    assert summary["averages"] == {"ctr": None, "cpc": None, "cpa": None, "roas": None}


@pytest.mark.django_db
def test_get_trends_sums_metric_per_day(seeded_records):
    trends = get_trends(granularity="day", metric="revenue", date_to="2026-01-02")

    assert trends == [
        {"period": "2026-01-01", "value": 600.0},
        {"period": "2026-01-02", "value": 750.0},
    ]


@pytest.mark.django_db
def test_get_trends_invalid_metric_raises(seeded_records):
    with pytest.raises(ValueError, match="Unknown metric"):
        get_trends(metric="not_a_metric")


@pytest.mark.django_db
def test_get_trends_empty_data_returns_empty_list():
    assert get_trends() == []


@pytest.mark.django_db
def test_get_top_campaigns_ranks_by_metric(seeded_records):
    top = get_top_campaigns(metric="revenue", limit=2)

    assert [c["campaign_name"] for c in top] == ["Campaign A", "Campaign B"]
    assert top[0]["revenue"] == 1250.0
    assert top[0]["cost"] == 125.0
    assert top[0]["impressions"] == 2500


@pytest.mark.django_db
def test_get_available_channels_and_date_range(seeded_records):
    assert get_available_channels() == ["Facebook Ads", "Google Ads"]
    assert get_date_range() == {"min_date": "2026-01-01", "max_date": "2026-01-08"}
