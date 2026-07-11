from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from analytics.models import CampaignRecord, DataSource

REQUIRED_COLUMNS = {
    "date",
    "channel",
    "campaign_name",
    "impressions",
    "clicks",
    "cost",
    "conversions",
    "revenue",
}
NUMERIC_COLUMNS = ["impressions", "clicks", "cost", "conversions", "revenue"]


class IngestionError(Exception):
    """Raised when a CSV can't be parsed or doesn't match the expected schema."""


@dataclass
class IngestionResult:
    rows_total: int
    rows_created: int
    rows_dropped_empty: int
    rows_dropped_invalid: int
    rows_dropped_duplicate: int

    @property
    def rows_dropped(self) -> int:
        return self.rows_dropped_empty + self.rows_dropped_invalid + self.rows_dropped_duplicate


def clean_campaign_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Normalize, validate, and de-duplicate raw campaign CSV rows.

    Pure pandas transformation with no Django/DB dependency, so it can be
    unit tested without a database.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise IngestionError(f"Missing required columns: {', '.join(sorted(missing))}")

    rows_total = len(df)

    df = df.dropna(how="all")
    rows_dropped_empty = rows_total - len(df)

    df["channel"] = df["channel"].astype(str).str.strip()
    df["campaign_name"] = df["campaign_name"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    blank = {"", "nan", "none", "null"}
    invalid_mask = (
        df["date"].isna()
        | df["channel"].str.lower().isin(blank)
        | df["campaign_name"].str.lower().isin(blank)
        | df[NUMERIC_COLUMNS].isna().any(axis=1)
        | (df[NUMERIC_COLUMNS] < 0).any(axis=1)
    )
    rows_dropped_invalid = int(invalid_mask.sum())
    df = df[~invalid_mask]

    rows_before_dedup = len(df)
    df = df.drop_duplicates(subset=["date", "channel", "campaign_name"], keep="first")
    rows_dropped_duplicate = rows_before_dedup - len(df)

    stats = {
        "rows_total": rows_total,
        "rows_dropped_empty": rows_dropped_empty,
        "rows_dropped_invalid": rows_dropped_invalid,
        "rows_dropped_duplicate": rows_dropped_duplicate,
    }
    return df, stats


def ingest_csv(file, data_source: DataSource) -> IngestionResult:
    """Parse, clean, and persist a CSV upload as CampaignRecord rows.

    Updates `data_source.status`/`row_count`/`error_message` to reflect the
    outcome, then returns a summary of what was created and dropped.
    """
    try:
        df = pd.read_csv(file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        data_source.status = DataSource.Status.FAILED
        data_source.error_message = f"Could not parse CSV: {exc}"
        data_source.save(update_fields=["status", "error_message"])
        raise IngestionError(str(exc)) from exc

    try:
        cleaned, stats = clean_campaign_data(df)
    except IngestionError as exc:
        data_source.status = DataSource.Status.FAILED
        data_source.error_message = str(exc)
        data_source.save(update_fields=["status", "error_message"])
        raise

    records = [
        CampaignRecord(
            data_source=data_source,
            date=row.date.date(),
            channel=row.channel,
            campaign_name=row.campaign_name,
            impressions=int(row.impressions),
            clicks=int(row.clicks),
            cost=Decimal(str(round(row.cost, 2))),
            conversions=int(row.conversions),
            revenue=Decimal(str(round(row.revenue, 2))),
        )
        for row in cleaned.itertuples()
    ]
    CampaignRecord.objects.bulk_create(records)

    data_source.status = DataSource.Status.PROCESSED
    data_source.row_count = len(records)
    data_source.save(update_fields=["status", "row_count"])

    return IngestionResult(
        rows_total=stats["rows_total"],
        rows_created=len(records),
        rows_dropped_empty=stats["rows_dropped_empty"],
        rows_dropped_invalid=stats["rows_dropped_invalid"],
        rows_dropped_duplicate=stats["rows_dropped_duplicate"],
    )
