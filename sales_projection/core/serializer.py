from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, date
import math

def _is_nan(x: Any) -> bool:
    try:
        return isinstance(x, float) and math.isnan(x)
    except Exception:
        return False

def json_safe(obj: Any) -> Any:
    """
    Convert ANY object into something json.dump/jsonify can handle:
    - pandas DataFrame/Series -> list/dicts
    - datetime/Timestamp -> ISO string
    - numpy -> python native
    - NaN -> None  (IMPORTANT: fixes invalid JSON NaN)
    - dataclass/object -> dict
    """
    # None
    if obj is None:
        return None

    # NaN -> None
    if _is_nan(obj):
        return None

    # datetime/date -> str
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # pandas Timestamp / DataFrame / Series
    try:
        import pandas as pd

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()

        if isinstance(obj, pd.DataFrame):
            # convert all values inside rows too
            rows = obj.to_dict(orient="records")
            return json_safe(rows)

        if isinstance(obj, pd.Series):
            return json_safe(obj.tolist())
    except Exception:
        pass

    # numpy types
    try:
        import numpy as np

        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()

        if isinstance(obj, np.ndarray):
            return json_safe(obj.tolist())
    except Exception:
        pass

    # dict
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]

    # dataclass
    if is_dataclass(obj):
        return json_safe(asdict(obj))

    # generic object
    if hasattr(obj, "__dict__"):
        return json_safe(vars(obj))

    # primitive types (str/int/bool/float)
    return obj


def forecastresult_to_payload(
    fr: Any,
    *,
    freq: str,
    filters: Dict[str, str],
    source: str = "engine",
) -> Dict[str, Any]:
    """
    Convert ForecastResult (your ML output) into the FINAL API schema
    expected by your wizard.js frontend + service.py scenario/insights.
    """
    # Your ForecastResult has: actual_df (ds,y), forecast_df (ds,yhat)
    actual_df = getattr(fr, "actual_df", None)
    forecast_df = getattr(fr, "forecast_df", None)

    if actual_df is None or forecast_df is None:
        raise ValueError("ForecastResult missing actual_df / forecast_df")

    # Convert dfs -> records
    actual_rows = json_safe(actual_df)  # list[dict]
    forecast_rows = json_safe(forecast_df)

    # Make chart series
    chart_actual = [{"date": r["ds"][:10], "value": float(r["y"])} for r in actual_rows]
    chart_forecast = [{"date": r["ds"][:10], "value": float(r["yhat"])} for r in forecast_rows]

    # Table (future forecast list)
    table = [{"date": r["ds"][:10], "predicted_sales": float(r["yhat"])} for r in forecast_rows]

    # KPI: last 3 actual + next 3 forecast
    last3_actual = sum(float(r["y"]) for r in actual_rows[-3:]) if len(actual_rows) >= 3 else sum(float(r["y"]) for r in actual_rows)
    next3_forecast = sum(float(r["yhat"]) for r in forecast_rows[:3]) if len(forecast_rows) >= 3 else sum(float(r["yhat"]) for r in forecast_rows)

    growth_pct = None
    if last3_actual and last3_actual != 0:
        growth_pct = (next3_forecast - last3_actual) / last3_actual * 100.0

    # Year table (simple, works for monthly; for weekly we’ll still show year totals)
    year_map: Dict[int, Dict[str, float]] = {}
    for r in actual_rows:
        y = int(r["ds"][:4])
        year_map.setdefault(y, {"actual": 0.0, "forecast": 0.0})
        year_map[y]["actual"] += float(r["y"])

    for r in forecast_rows:
        y = int(r["ds"][:4])
        year_map.setdefault(y, {"actual": 0.0, "forecast": 0.0})
        year_map[y]["forecast"] += float(r["yhat"])

    year_table = []
    for y in sorted(year_map.keys()):
        a = year_map[y]["actual"]
        f = year_map[y]["forecast"]
        year_table.append(
            {"year": y, "actual_sales": a, "forecast_sales": f, "total": a + f}
        )

    payload = {
        "freq": freq,
        "filters": filters,
        "source": source,
        "chart": {"actual": chart_actual, "forecast": chart_forecast},
        "kpis": {
            "last_periods_actual": last3_actual,
            "next_periods_forecast": next3_forecast,
            "growth_pct": growth_pct if growth_pct is not None else 0.0,
        },
        "table": table,
        "year_table": year_table,
        "insights": {  # service.py will fill these
            "best_predicted": {"best_date": None, "best_value": None},
            "seasonality": {"top_month_names": [], "default_note": ""},
            "anomaly": {"is_anomaly": False, "message": ""},
            "recommendations": [],
        },
        "meta": {
            "freq": freq,
            "filters": filters,
        },
    }

    return json_safe(payload)


def engine_to_payload(
    raw: Any,
    *,
    freq: str,
    filters: Dict[str, str],
    source: str = "engine",
) -> Dict[str, Any]:
    """
    One entry point:
    - If raw is ForecastResult -> convert
    - If raw is already dict but wrong keys -> attempt adapt
    """
    if isinstance(raw, dict):
        # If it already matches final schema, keep it.
        if "chart" in raw and "table" in raw:
            return json_safe(raw)

        # If it is the old shape with actual_df/forecast_df keys:
        if "actual_df" in raw and "forecast_df" in raw:
            class _Tmp:
                pass
            tmp = _Tmp()
            tmp.actual_df = raw["actual_df"]
            tmp.forecast_df = raw["forecast_df"]
            return forecastresult_to_payload(tmp, freq=freq, filters=filters, source=source)

        return json_safe(raw)

    # ForecastResult-like object
    if hasattr(raw, "actual_df") and hasattr(raw, "forecast_df"):
        return forecastresult_to_payload(raw, freq=freq, filters=filters, source=source)

    # fallback
    safe = json_safe(raw)
    return safe if isinstance(safe, dict) else {"result": safe}
