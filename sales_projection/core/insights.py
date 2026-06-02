from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import statistics


@dataclass
class Confidence:
    label: str
    note: str


def _clean(values: List[float]) -> list[float]:
    out = []
    for v in values:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def compute_confidence(history_values: List[float], freq: str) -> Confidence:
    vals = _clean(history_values)
    n = len(vals)

    if n < 6:
        return Confidence("Low", "Very short history. Forecast may be unreliable.")

    mean = statistics.fmean(vals) if n else 0.0
    std = statistics.pstdev(vals) if n > 1 else 0.0
    cv = (std / mean) if mean > 0 else 1.0

    if freq == "weekly":
        length_score = 2 if n >= 52 else (1 if n >= 26 else 0)
    else:
        length_score = 2 if n >= 36 else (1 if n >= 18 else 0)

    if cv <= 0.35:
        vol_score = 2
    elif cv <= 0.60:
        vol_score = 1
    else:
        vol_score = 0

    score = length_score + vol_score
    if score >= 3:
        return Confidence("High", "Good history length and stable trend/seasonality.")
    if score == 2:
        return Confidence("Medium", "Decent history, but some volatility is present.")
    return Confidence("Low", "Short history and/or high volatility. Use with caution.")


def build_seasonality_insight(history_dates: List[str], history_values: List[float]) -> Dict[str, Any]:
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    by_month = {i: [] for i in range(1, 13)}

    for d, v in zip(history_dates, history_values):
        if v is None:
            continue
        try:
            m = int(str(d)[5:7])
            if 1 <= m <= 12:
                by_month[m].append(float(v))
        except Exception:
            continue

    month_avg = []
    for m, arr in by_month.items():
        if arr:
            month_avg.append((m, statistics.fmean(arr)))

    month_avg.sort(key=lambda x: x[1], reverse=True)
    top = [month_names[m - 1] for (m, _) in month_avg[:3]]

    return {
        "top_month_names": top,
        "default_note": "Historically highest sales often occur in Nov/Dec (seasonal peak).",
    }


def anomaly_insight(history_values: List[float]) -> Dict[str, Any]:
    vals = _clean(history_values)
    if len(vals) < 6:
        return {"is_anomaly": False, "message": ""}

    last = vals[-1]
    previous = vals[:-1]
    mean = statistics.fmean(previous)
    std = statistics.pstdev(previous) if len(previous) > 1 else 0.0

    if std <= 1e-9:
        return {"is_anomaly": False, "message": ""}

    z = (last - mean) / std
    if abs(z) >= 2.2:
        direction = "high" if z > 0 else "low"
        return {
            "is_anomaly": True,
            "message": f"Last period unusually {direction} vs average (z={z:.1f}).",
        }
    return {"is_anomaly": False, "message": ""}


def best_predicted_insight(forecast_dates: List[str], forecast_values: List[float]) -> Dict[str, Any]:
    if not forecast_dates or not forecast_values:
        return {"best_date": None, "best_value": None}
    idx = max(range(len(forecast_values)), key=lambda i: float(forecast_values[i]))
    return {"best_date": forecast_dates[idx], "best_value": float(forecast_values[idx])}


def recommendations_from_forecast(freq: str, growth_pct: Optional[float], seasonality_top: List[str]) -> List[str]:
    recs = []

    if growth_pct is None:
        recs.append("Forecast generated. Consider adding more history for more reliable insights.")
        return recs

    if growth_pct >= 8:
        recs.append("Plan inventory and staffing for expected growth in upcoming periods.")
    elif growth_pct <= -5:
        recs.append("Consider promotions, pricing review, or bundling to address expected slowdown.")
    else:
        recs.append("Maintain current strategy; monitor weekly/monthly performance and adjust marketing spend.")

    if "Nov" in seasonality_top or "Dec" in seasonality_top:
        recs.append("Prepare for seasonal peak (Nov-Dec): stock up and plan campaigns early.")

    if freq == "weekly":
        recs.append("Track week-to-week volatility; adjust operations quickly based on short-term signals.")
    else:
        recs.append("Use monthly projections to plan budget, inventory, and target-based performance reviews.")

    return recs
