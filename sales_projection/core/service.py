from __future__ import annotations

from typing import Dict, Any
import copy
import os
import json
import hashlib

from .serializer import json_safe, engine_to_payload

from .insights import (
    compute_confidence,
    build_seasonality_insight,
    anomaly_insight,
    best_predicted_insight,
    recommendations_from_forecast,
)

SCENARIO_FACTOR = {
    "conservative": 0.92,
    "base": 1.00,
    "aggressive": 1.08,
}


def _safe_scenario(s: str) -> str:
    s = (s or "base").strip().lower()
    return s if s in SCENARIO_FACTOR else "base"


def _cache_key(params: Dict[str, str]) -> str:
    normalized = "|".join([f"{k}={params.get(k,'')}" for k in sorted(params.keys())])
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _read_json(path: str) -> Dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    safe = json_safe(data)

    # IMPORTANT: allow_nan=False forces us to remove NaN (we already do -> None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, ensure_ascii=False, allow_nan=False)


def apply_scenario(payload: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    scenario = _safe_scenario(scenario)
    factor = SCENARIO_FACTOR[scenario]

    out = copy.deepcopy(payload)
    out["scenario"] = scenario

    # Forecast chart
    for p in out.get("chart", {}).get("forecast", []):
        p["value"] = float(p["value"]) * factor

    # Table
    for r in out.get("table", []):
        r["predicted_sales"] = float(r["predicted_sales"]) * factor

    # Year table
    for r in out.get("year_table", []):
        r["forecast_sales"] = float(r["forecast_sales"]) * factor
        r["total"] = float(r["actual_sales"]) + float(r["forecast_sales"])

    # KPIs
    kpis = out.get("kpis", {})
    if out.get("table"):
        next3 = sum(float(r.get("predicted_sales", 0.0)) for r in out["table"][:3])
        kpis["next_periods_forecast"] = float(next3)

    last_actual = kpis.get("last_periods_actual", None)
    next_fore = kpis.get("next_periods_forecast", None)
    if last_actual is not None and next_fore is not None and float(last_actual) != 0:
        kpis["growth_pct"] = (float(next_fore) - float(last_actual)) / float(last_actual) * 100.0
    out["kpis"] = kpis

    # Best predicted
    f = out.get("chart", {}).get("forecast", [])
    fdates = [p.get("date") for p in f]
    fvals = [p.get("value") for p in f]
    out.setdefault("insights", {})
    out["insights"]["best_predicted"] = best_predicted_insight(fdates, fvals)

    return out


def enrich_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(payload)

    freq = out.get("freq", "monthly")
    chart = out.get("chart", {})
    actual = chart.get("actual", [])
    forecast = chart.get("forecast", [])

    history_dates = [p.get("date") for p in actual]
    history_values = [p.get("value") for p in actual]
    forecast_dates = [p.get("date") for p in forecast]
    forecast_values = [p.get("value") for p in forecast]

    seas = build_seasonality_insight(history_dates, history_values)
    anom = anomaly_insight(history_values)
    best = best_predicted_insight(forecast_dates, forecast_values)

    kpis = out.get("kpis", {})
    growth = kpis.get("growth_pct", None)

    recs = recommendations_from_forecast(freq, growth, seas.get("top_month_names", []))
    out.setdefault("insights", {})
    out["insights"]["seasonality"] = seas
    out["insights"]["anomaly"] = anom
    out["insights"]["best_predicted"] = best
    out["insights"]["recommendations"] = recs

    conf = compute_confidence(history_values, freq)
    out["confidence"] = {"label": conf.label, "note": conf.note}

    return out


def run_forecast(
    engine_forecast_fn,
    cache_dir: str,
    params: Dict[str, str],
) -> Dict[str, Any]:
    scenario = _safe_scenario(params.get("scenario", "base"))
    params2 = dict(params)
    params2["scenario"] = scenario

    key = _cache_key(params2)
    cache_path = os.path.join(cache_dir, f"{key}.json")

    cached = _read_json(cache_path)
    if cached:
        cached["cache_hit"] = True
        return cached

    # 1) engine output (ForecastResult OR dict)
    raw = engine_forecast_fn(params2)

    # 2) Convert ONCE -> final payload schema
    freq = params2.get("freq", "monthly")
    filters = {
        "category": params2.get("category", "All"),
        "region": params2.get("region", "All"),
        "segment": params2.get("segment", "All"),
    }
    base = engine_to_payload(raw, freq=freq, filters=filters, source="engine")
    base["cache_hit"] = False

    # 3) Apply scenario + insights
    base = apply_scenario(base, scenario)
    base = enrich_insights(base)

    # 4) Final safety (no pandas/numpy/NaN)
    base = json_safe(base)

    _write_json(cache_path, base)
    return base
