import pandas as pd
from django.db.models import Max, Min

from analytics.models import CampaignRecord

METRIC_COLUMNS = ["impressions", "clicks", "cost", "conversions", "revenue"]
GRANULARITY_FREQ = {"day": "D", "week": "W-MON", "month": "MS"}


def _load_dataframe(date_from=None, date_to=None, channel=None) -> pd.DataFrame:
    qs = CampaignRecord.objects.all()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if channel:
        qs = qs.filter(channel=channel)

    df = pd.DataFrame.from_records(
        qs.values("date", "channel", "campaign_name", *METRIC_COLUMNS)
    )
    if df.empty:
        return pd.DataFrame(columns=["date", "channel", "campaign_name", *METRIC_COLUMNS])

    df["date"] = pd.to_datetime(df["date"])
    for col in ("cost", "revenue"):
        df[col] = df[col].astype(float)
    return df


def _safe_ratio(numerator: float, denominator: float, digits: int = 4):
    if not denominator:
        return None
    return round(numerator / denominator, digits)


def get_summary(date_from=None, date_to=None, channel=None) -> dict:
    """Totals and derived rate metrics (CTR, CPC, CPA, ROAS) for the given filters."""
    df = _load_dataframe(date_from, date_to, channel)

    totals = {
        "impressions": int(df["impressions"].sum()),
        "clicks": int(df["clicks"].sum()),
        "cost": round(float(df["cost"].sum()), 2),
        "conversions": int(df["conversions"].sum()),
        "revenue": round(float(df["revenue"].sum()), 2),
    }
    averages = {
        "ctr": _safe_ratio(totals["clicks"], totals["impressions"]),
        "cpc": _safe_ratio(totals["cost"], totals["clicks"]),
        "cpa": _safe_ratio(totals["cost"], totals["conversions"]),
        "roas": _safe_ratio(totals["revenue"], totals["cost"]),
    }
    return {
        "date_from": date_from,
        "date_to": date_to,
        "channel": channel,
        "row_count": len(df),
        "totals": totals,
        "averages": averages,
    }


def get_trends(granularity="day", metric="revenue", date_from=None, date_to=None, channel=None) -> list[dict]:
    """Time series of `metric` summed per period, at day/week/month granularity."""
    if metric not in METRIC_COLUMNS:
        raise ValueError(f"Unknown metric '{metric}'. Choose one of: {', '.join(METRIC_COLUMNS)}")
    if granularity not in GRANULARITY_FREQ:
        raise ValueError(f"Unknown granularity '{granularity}'. Choose one of: {', '.join(GRANULARITY_FREQ)}")

    df = _load_dataframe(date_from, date_to, channel)
    if df.empty:
        return []

    series = df.set_index("date").resample(GRANULARITY_FREQ[granularity])[metric].sum()
    return [{"period": period.date().isoformat(), "value": round(float(value), 2)} for period, value in series.items()]


def get_top_campaigns(metric="revenue", limit=5, date_from=None, date_to=None, channel=None) -> list[dict]:
    """Campaigns ranked by total `metric`, aggregated across the given date/channel filters."""
    if metric not in METRIC_COLUMNS:
        raise ValueError(f"Unknown metric '{metric}'. Choose one of: {', '.join(METRIC_COLUMNS)}")

    df = _load_dataframe(date_from, date_to, channel)
    if df.empty:
        return []

    grouped = (
        df.groupby(["campaign_name", "channel"], as_index=False)[METRIC_COLUMNS]
        .sum()
        .sort_values(metric, ascending=False)
        .head(limit)
    )

    records = []
    for row in grouped.itertuples(index=False):
        records.append(
            {
                "campaign_name": row.campaign_name,
                "channel": row.channel,
                "impressions": int(row.impressions),
                "clicks": int(row.clicks),
                "cost": round(float(row.cost), 2),
                "conversions": int(row.conversions),
                "revenue": round(float(row.revenue), 2),
            }
        )
    return records


def get_available_channels() -> list[str]:
    return list(
        CampaignRecord.objects.order_by("channel").values_list("channel", flat=True).distinct()
    )


def get_date_range() -> dict:
    agg = CampaignRecord.objects.aggregate(min_date=Min("date"), max_date=Max("date"))
    return {
        "min_date": agg["min_date"].isoformat() if agg["min_date"] else None,
        "max_date": agg["max_date"].isoformat() if agg["max_date"] else None,
    }
