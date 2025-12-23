from __future__ import annotations

import numpy as np
import pandas as pd


def make_time_features(ds: pd.Series) -> pd.DataFrame:
    """Calendar + basic seasonality features."""
    dt = pd.to_datetime(ds)
    out = pd.DataFrame(index=ds.index)

    out["year"] = dt.dt.year
    out["month"] = dt.dt.month
    out["quarter"] = dt.dt.quarter
    out["day_of_week"] = dt.dt.dayofweek
    out["day_of_month"] = dt.dt.day
    out["week_of_year"] = dt.dt.isocalendar().week.astype(int)

    # Simple cyclic encodings
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12.0)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12.0)
    out["week_sin"] = np.sin(2 * np.pi * out["week_of_year"] / 52.0)
    out["week_cos"] = np.cos(2 * np.pi * out["week_of_year"] / 52.0)

    # Business-friendly flags
    out["is_q4"] = (out["quarter"] == 4).astype(int)
    out["is_nov_dec"] = out["month"].isin([11, 12]).astype(int)

    return out


def add_lag_rolling_features(series_df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Given a series dataframe with columns ds, y, add lag and rolling features.

    Drops rows that don't have enough history for the chosen lags/windows.
    """
    freq = freq.lower().strip()
    if freq not in {"weekly", "monthly", "yearly"}:
        raise ValueError(f"Unsupported freq: {freq}")

    out = series_df.copy()

    if freq == "weekly":
        lag_list = [1, 2, 3, 4, 8, 13]
        roll_windows = [4, 8, 13]
    else:
        lag_list = [1, 2, 3, 6, 12]
        roll_windows = [3, 6, 12]

    for l in lag_list:
        out[f"lag_{l}"] = out["y"].shift(l)

    for w in roll_windows:
        shifted = out["y"].shift(1)
        out[f"roll_mean_{w}"] = shifted.rolling(w).mean()
        out[f"roll_std_{w}"] = shifted.rolling(w).std()
        out[f"roll_sum_{w}"] = shifted.rolling(w).sum()

    tf = make_time_features(out["ds"])
    out = pd.concat([out, tf], axis=1)

    out = out.dropna().reset_index(drop=True)
    return out


def build_supervised_matrix(series_df: pd.DataFrame, freq: str):
    """Return X, y and the feature frame used for training/inference."""
    feat_df = add_lag_rolling_features(series_df, freq=freq)
    feature_cols = [c for c in feat_df.columns if c not in {"ds", "y"}]
    X = feat_df[feature_cols].astype(float)
    y = feat_df["y"].astype(float)
    return X, y, feature_cols, feat_df
