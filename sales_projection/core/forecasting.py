from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import add_lag_rolling_features, build_supervised_matrix
from .model import TrainedModel, train_xgb


@dataclass
class ForecastResult:
    actual_df: pd.DataFrame
    forecast_df: pd.DataFrame
    trained: TrainedModel


def _step_offset(freq: str):
    freq = (freq or "").lower().strip()
    if freq == "weekly":
        return pd.DateOffset(weeks=1)
    # monthly & yearly use month-start steps
    return pd.DateOffset(months=1)


def _weekly_rule_from_data(idx: pd.DatetimeIndex) -> str:
    """
    IMPORTANT FIX:
    Your app.py resamples weekly using 'W' (week ends on Sunday by default),
    which produces dates like 2014-01-05, 2014-01-12, ...
    But earlier we aligned to 'W-MON', which reindex-mismatched and turned everything into NaN -> 0.

    This function picks the correct weekly anchor from the data itself, so reindex matches.
    """
    if len(idx) == 0:
        return "W-SUN"

    # choose the weekday of the first timestamp as the anchor
    # pandas expects: W-MON, W-TUE, ... W-SUN
    anchor = idx[0].strftime("%a").upper()  # e.g., 'SUN', 'MON'
    if anchor not in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}:
        anchor = "SUN"
    return f"W-{anchor}"


def _align_series(series_df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Ensure ds is a regular frequency index and missing periods are filled with 0 sales."""
    freq = (freq or "").lower().strip()

    tmp = series_df.copy()
    tmp["ds"] = pd.to_datetime(tmp["ds"])
    tmp = tmp.sort_values("ds").set_index("ds")

    if freq == "weekly":
        # ✅ FIX: match weekly anchor to the data (prevents all-zeros)
        rule = _weekly_rule_from_data(tmp.index)
    else:
        # monthly & yearly both use month-start index
        rule = "MS"

    full_idx = pd.date_range(tmp.index.min(), tmp.index.max(), freq=rule)

    # reindex and fill missing periods with 0
    tmp = tmp.reindex(full_idx)
    tmp.index.name = "ds"
    tmp["y"] = tmp["y"].fillna(0.0)
    tmp = tmp.reset_index()
    tmp["y"] = tmp["y"].astype(float)
    return tmp


def recursive_forecast(series_df: pd.DataFrame, freq: str, horizon: int, xgb_params: dict) -> ForecastResult:
    """Train XGBoost on a single aggregated series and produce a multi-step forecast."""
    freq = (freq or "").lower().strip()
    if horizon <= 0:
        raise ValueError("horizon must be > 0")

    actual = _align_series(series_df[["ds", "y"]], freq)

    # Train on all available points that have features
    X, y, feature_cols, feat_df = build_supervised_matrix(actual, freq=freq)
    model = train_xgb(X, y, xgb_params)
    trained = TrainedModel(model=model, feature_cols=feature_cols)

    # Start with the full actual series and append predictions recursively
    history = actual.copy()
    offset = _step_offset(freq)

    preds = []
    last_ds = pd.to_datetime(history["ds"].iloc[-1])

    for step in range(1, horizon + 1):
        next_ds = last_ds + offset

        # Append a placeholder row; y will be predicted
        history = pd.concat(
            [history, pd.DataFrame({"ds": [next_ds], "y": [None]})],
            ignore_index=True,
        )

        # Build features for the whole history, take the last row as prediction row
        feat_history = add_lag_rolling_features(history.ffill(), freq=freq)

        # Get the row for next_ds
        row = feat_history[feat_history["ds"] == next_ds]
        if row.empty:
            raise ValueError(
                "Not enough history to build lag features for forecasting. "
                "Try selecting 'All' filters or use broader filters."
            )

        X_row = row[feature_cols].astype(float).values
        yhat = float(trained.model.predict(X_row)[0])

        # Set prediction into history
        history.loc[history["ds"] == next_ds, "y"] = yhat
        preds.append({"ds": next_ds, "yhat": yhat})
        last_ds = next_ds

    forecast_df = pd.DataFrame(preds)
    return ForecastResult(actual_df=actual, forecast_df=forecast_df, trained=trained)
