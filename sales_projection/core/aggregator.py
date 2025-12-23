from __future__ import annotations

import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    category: str = "All",
    region: str = "All",
    segment: str = "All",
) -> pd.DataFrame:
    """Filter a Superstore dataframe by category/region/segment.

    Each filter accepts a specific value or "All".
    """
    out = df
    if category and category != "All":
        out = out[out["category"] == category]
    if region and region != "All":
        out = out[out["region"] == region]
    if segment and segment != "All":
        out = out[out["segment"] == segment]
    return out


def aggregate_sales(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate filtered data to a single time series.

    Returns a dataframe with columns:
      - ds: period start date (timestamp)
      - y: aggregated sales (float)

    freq:
      - weekly: week start (Mon)
      - monthly: month start
      - yearly: month start (still monthly output, 12 months horizon)

    Note: yearly mode is simply monthly aggregation with a 12-month forecast horizon.
    """
    freq = freq.lower().strip()
    if freq not in {"weekly", "monthly", "yearly"}:
        raise ValueError(f"Unsupported freq: {freq}")

    df = df.copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    if freq == "weekly":
        # W-MON = weekly periods starting on Monday
        grouped = (
            df.set_index("order_date")["sales"]
            .resample("W-MON")
            .sum()
            .reset_index()
            .rename(columns={"order_date": "ds", "sales": "y"})
        )
    else:
        grouped = (
            df.set_index("order_date")["sales"]
            .resample("MS")
            .sum()
            .reset_index()
            .rename(columns={"order_date": "ds", "sales": "y"})
        )

    grouped["y"] = grouped["y"].astype(float)
    grouped.sort_values("ds", inplace=True)
    grouped.reset_index(drop=True, inplace=True)
    return grouped
