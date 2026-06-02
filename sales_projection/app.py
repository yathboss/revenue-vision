from __future__ import annotations

import io
import sys
import csv
import statistics
from collections import defaultdict
from calendar import monthrange
from datetime import datetime, datetime as dt
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request, send_file, Response
from flask.json.provider import DefaultJSONProvider

try:
    from sales_projection.config import CACHE_DIR
    from sales_projection.core.service import run_forecast
except ModuleNotFoundError:
    from config import CACHE_DIR
    from core.service import run_forecast


KAGGLE_URL = "https://www.kaggle.com/datasets/vivek468/superstore-dataset-final"


def ensure_dict(x):
    if isinstance(x, dict):
        return x
    if is_dataclass(x):
        return asdict(x)
    if hasattr(x, "to_dict"):
        try:
            return x.to_dict()
        except Exception:
            pass
    if hasattr(x, "__dict__"):
        return dict(x.__dict__)
    return {"result": str(x)}


# ------------------------------------------------------------------
# ADAPTER: query params -> series_df + horizon + xgb_params + freq
# ------------------------------------------------------------------
def forecast_query(params: dict):
    freq = (params.get("freq") or "monthly").lower()
    horizon = 13 if freq == "weekly" else 12

    data_path = Path(__file__).resolve().parent / "data" / "superstore.csv"
    if not data_path.exists():
        data_path = Path("data/superstore.csv")
    if not data_path.exists():
        data_path = Path("sales_projection/data/superstore.csv")

    category = params.get("category", "All")
    region = params.get("region", "All")
    segment = params.get("segment", "All")

    grouped: dict[date, float] = defaultdict(float)
    with data_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = csv.DictReader(f)
        for row in rows:
            if category != "All" and row.get("Category") != category:
                continue
            if region != "All" and row.get("Region") != region:
                continue
            if segment != "All" and row.get("Segment") != segment:
                continue

            raw_date = row.get("Order Date") or row.get("order_date")
            raw_sales = row.get("Sales") or row.get("sales")
            if not raw_date or not raw_sales:
                continue

            order_date = date.fromisoformat(raw_date[:10])
            if freq == "weekly":
                period = order_date - timedelta(days=order_date.weekday())
            else:
                period = order_date.replace(day=1)
            grouped[period] += float(raw_sales)

    if not grouped:
        raise ValueError("No data found for selected filters. Try selecting All.")

    actual_rows = sorted(grouped.items())
    if len(actual_rows) < 6:
        raise ValueError("Not enough history for forecast. Try broader filters or All.")

    actual_values = [v for _, v in actual_rows]
    forecast_dates = _future_periods(actual_rows[-1][0], horizon, freq)
    forecast_values = _forecast_values(actual_rows, forecast_dates, freq)

    chart_actual = [{"date": d.isoformat(), "value": float(v)} for d, v in actual_rows]
    chart_forecast = [{"date": d.isoformat(), "value": float(v)} for d, v in zip(forecast_dates, forecast_values)]
    table = [{"date": d.isoformat(), "predicted_sales": float(v)} for d, v in zip(forecast_dates, forecast_values)]

    last3_actual = sum(actual_values[-3:])
    next3_forecast = sum(forecast_values[:3])
    growth_pct = ((next3_forecast - last3_actual) / last3_actual * 100.0) if last3_actual else 0.0

    year_map: dict[int, dict[str, float]] = defaultdict(lambda: {"actual_sales": 0.0, "forecast_sales": 0.0})
    for d, v in actual_rows:
        year_map[d.year]["actual_sales"] += float(v)
    for d, v in zip(forecast_dates, forecast_values):
        year_map[d.year]["forecast_sales"] += float(v)

    year_table = []
    for year in sorted(year_map):
        actual = year_map[year]["actual_sales"]
        forecast = year_map[year]["forecast_sales"]
        year_table.append({"year": year, "actual_sales": actual, "forecast_sales": forecast, "total": actual + forecast})

    return {
        "freq": freq,
        "filters": {"category": category, "region": region, "segment": segment},
        "source": "lightweight",
        "chart": {"actual": chart_actual, "forecast": chart_forecast},
        "kpis": {
            "last_periods_actual": last3_actual,
            "next_periods_forecast": next3_forecast,
            "growth_pct": growth_pct,
        },
        "table": table,
        "year_table": year_table,
        "insights": {
            "best_predicted": {"best_date": None, "best_value": None},
            "seasonality": {"top_month_names": [], "default_note": ""},
            "anomaly": {"is_anomaly": False, "message": ""},
            "recommendations": [],
        },
    }


def _future_periods(last_period: date, horizon: int, freq: str) -> list[date]:
    if freq == "weekly":
        return [last_period + timedelta(days=7 * i) for i in range(1, horizon + 1)]

    out = []
    year = last_period.year
    month = last_period.month
    for _ in range(horizon):
        month += 1
        if month > 12:
            month = 1
            year += 1
        out.append(date(year, month, 1))
    return out


def _forecast_values(actual_rows: list[tuple[date, float]], forecast_dates: list[date], freq: str) -> list[float]:
    values = [v for _, v in actual_rows]
    recent = values[-6:] if len(values) >= 6 else values
    previous = values[-12:-6] if len(values) >= 12 else values[:-6]
    recent_avg = statistics.fmean(recent)
    previous_avg = statistics.fmean(previous) if previous else recent_avg
    trend = recent_avg / previous_avg if previous_avg else 1.0
    trend = max(0.80, min(1.20, trend))

    if freq == "weekly":
        base = statistics.fmean(values[-8:] if len(values) >= 8 else values)
        return [max(0.0, base * (trend ** (i / 8))) for i in range(1, len(forecast_dates) + 1)]

    by_month: dict[int, list[float]] = defaultdict(list)
    for d, v in actual_rows:
        by_month[d.month].append(v)

    forecasts = []
    for i, d in enumerate(forecast_dates, start=1):
        month_vals = by_month.get(d.month) or recent
        seasonal_base = statistics.fmean(month_vals)
        blended = (seasonal_base * 0.68) + (recent_avg * 0.32)
        forecasts.append(max(0.0, blended * (trend ** (i / 12))))
    return forecasts


# ------------------------------------------------------------------
# FLASK APP
# ------------------------------------------------------------------
def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="web/templates",
        static_folder="web/static",
    )

    # ✅ JSON provider for datetime/pandas Timestamp
    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, dt):
                return obj.isoformat()
            return super().default(obj)

    app.json = CustomJSONProvider(app)

    @app.get("/")
    def landing():
        return render_template("landing.html", kaggle_url=KAGGLE_URL)

    @app.get("/wizard")
    def wizard():
        try:
            from sales_projection.core.data_loader import get_filter_options
        except ModuleNotFoundError:
            from core.data_loader import get_filter_options
        opts = get_filter_options()
        return render_template(
            "wizard.html",
            opts=opts,
            categories=opts.get("categories", []),
            regions=opts.get("regions", []),
            segments=opts.get("segments", []),
        )

    @app.get("/about-model")
    def about_model():
        return render_template("about_model.html")

    @app.get("/how-to-use")
    def how_to_use():
        return render_template("how_to_use.html")

    # ----------------------------
    # FORECAST API
    # ----------------------------
    @app.get("/forecast")
    def forecast():
        params = {
            "freq": request.args.get("freq", "monthly"),
            "category": request.args.get("category", "All"),
            "region": request.args.get("region", "All"),
            "segment": request.args.get("segment", "All"),
            "mode": request.args.get("mode", "fast"),
            "scenario": request.args.get("scenario", "base"),
        }

        try:
            payload = run_forecast(
                engine_forecast_fn=forecast_query,
                cache_dir=str(CACHE_DIR),
                params=params,
            )
            payload = ensure_dict(payload)
            payload["mode"] = params["mode"]
            return jsonify(payload)
        except Exception as e:
            return jsonify({"message": str(e)}), 400

    # ----------------------------
    # DOWNLOAD CSV
    # ----------------------------
    @app.get("/download")
    def download_csv():
        params = {
            "freq": request.args.get("freq", "monthly"),
            "category": request.args.get("category", "All"),
            "region": request.args.get("region", "All"),
            "segment": request.args.get("segment", "All"),
            "mode": request.args.get("mode", "fast"),
            "scenario": request.args.get("scenario", "base"),
        }

        payload = run_forecast(
            engine_forecast_fn=forecast_query,
            cache_dir=str(CACHE_DIR),
            params=params,
        )
        payload = ensure_dict(payload)

        out = io.StringIO()
        out.write("date,predicted_sales\n")
        for r in payload.get("table", []):
            out.write(f"{r['date']},{r['predicted_sales']}\n")

        return Response(
            out.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=forecast.csv"},
        )

    # ----------------------------
    # PDF REPORT
    # ----------------------------
    @app.get("/report.pdf")
    def report_pdf():
        return jsonify({"message": "PDF export is unavailable on the Vercel deployment. Use CSV download instead."}), 501

        params = {
            "freq": request.args.get("freq", "monthly"),
            "category": request.args.get("category", "All"),
            "region": request.args.get("region", "All"),
            "segment": request.args.get("segment", "All"),
            "mode": request.args.get("mode", "fast"),
            "scenario": request.args.get("scenario", "base"),
        }

        payload = run_forecast(
            engine_forecast_fn=forecast_query,
            cache_dir=str(CACHE_DIR),
            params=params,
        )
        payload = ensure_dict(payload)

        chart = payload.get("chart", {}) or {}
        actual = chart.get("actual", []) or []
        forecast = chart.get("forecast", []) or []

        # ---- Build chart image (PNG in memory) with clean x-axis
        def _to_dt(v):
            if isinstance(v, str):
                return dt.fromisoformat(v[:10])
            return v

        x_actual = [_to_dt(p.get("date")) for p in actual]
        y_actual = [p.get("value", 0) for p in actual]
        x_fore = [_to_dt(p.get("date")) for p in forecast]
        y_fore = [p.get("value", 0) for p in forecast]

        fig = plt.figure(figsize=(9, 3))
        ax = fig.add_subplot(111)

        ax.plot(x_actual, y_actual, label="Actual")
        ax.plot(x_fore, y_fore, linestyle="--", label="Forecast")

        ax.legend()
        ax.grid(alpha=0.3)
        ax.set_title("Actual vs Forecast")

        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=30)

        img = io.BytesIO()
        fig.tight_layout()
        fig.savefig(img, format="png", dpi=150)
        plt.close(fig)
        img.seek(0)

        # ---- Create PDF
        pdf = io.BytesIO()
        c = pdf_canvas.Canvas(pdf, pagesize=A4)
        w, h = A4

        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2 * cm, h - 2 * cm, "Sales Projection — Forecast Report")

        c.setFont("Helvetica", 10)
        c.setFillColor(colors.grey)
        c.drawString(2 * cm, h - 2.7 * cm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.setFillColor(colors.black)

        # Params line
        c.setFont("Helvetica", 10)
        c.drawString(
            2 * cm,
            h - 3.3 * cm,
            f"Freq: {params['freq']} | Category: {params['category']} | Region: {params['region']} | Segment: {params['segment']}",
        )

        # Chart
        c.drawImage(ImageReader(img), 2 * cm, h - 11 * cm, width=17 * cm, height=6 * cm, mask="auto")

        # KPIs (formatted)
        k = payload.get("kpis", {}) or {}

        def fmt_money(v):
            return f"{v:,.0f}" if isinstance(v, (int, float)) else "—"

        def fmt_pct(v):
            return f"{v:.1f}%" if isinstance(v, (int, float)) else "—"

        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, h - 12.1 * cm, "KPIs")
        c.setFont("Helvetica", 11)
        c.drawString(2 * cm, h - 12.8 * cm, f"Last periods actual: {fmt_money(k.get('last_periods_actual'))}")
        c.drawString(2 * cm, h - 13.4 * cm, f"Next periods forecast: {fmt_money(k.get('next_periods_forecast'))}")
        c.drawString(2 * cm, h - 14.0 * cm, f"Growth %: {fmt_pct(k.get('growth_pct'))}")

        # Insights (formatted)
        ins = payload.get("insights", {}) or {}
        best = ins.get("best_predicted", {}) or {}
        season = ins.get("seasonality", {}) or {}
        anom = ins.get("anomaly", {}) or {}

        best_date = best.get("best_date", "—")
        best_val = best.get("best_value", None)
        best_val_txt = f"{best_val:,.0f}" if isinstance(best_val, (int, float)) else "—"

        top_months = season.get("top_month_names", []) or []
        top_months_txt = ", ".join(top_months) if top_months else "—"
        season_note = season.get("default_note", "") or ""

        anom_flag = anom.get("is_anomaly", False)
        anom_msg = anom.get("message", "") or ""
        anom_txt = "Yes" if anom_flag else "No"
        if anom_msg:
            anom_txt += f" — {anom_msg}"

        y = h - 15.0 * cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Insights")
        y -= 0.6 * cm

        c.setFont("Helvetica", 10)
        c.drawString(2 * cm, y, f"Best month predicted: {best_date} (Sales: {best_val_txt})")
        y -= 0.5 * cm
        c.drawString(2 * cm, y, f"Top seasonality months: {top_months_txt}")
        y -= 0.5 * cm

        if season_note:
            max_chars = 95
            note_lines = [season_note[i : i + max_chars] for i in range(0, len(season_note), max_chars)]
            c.drawString(2 * cm, y, f"Note: {note_lines[0]}")
            y -= 0.5 * cm
            for ln in note_lines[1:]:
                if y < 3 * cm:
                    c.showPage()
                    y = h - 3 * cm
                    c.setFont("Helvetica", 10)
                c.drawString(2 * cm, y, ln)
                y -= 0.5 * cm

        c.drawString(2 * cm, y, f"Anomaly detected: {anom_txt}")
        y -= 0.8 * cm

        # Recommendations
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Recommendations")
        y -= 0.6 * cm
        c.setFont("Helvetica", 10)

        recs = ins.get("recommendations", []) or []
        if not recs:
            c.drawString(2.4 * cm, y, "• —")
            y -= 0.45 * cm
        else:
            for r in recs[:20]:
                if y < 3 * cm:
                    c.showPage()
                    y = h - 3 * cm
                    c.setFont("Helvetica", 10)
                c.drawString(2.4 * cm, y, f"• {str(r)}")
                y -= 0.45 * cm

        # Footer
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2 * cm, 1.8 * cm, "Dataset Source:")
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.blue)
        c.drawString(5.2 * cm, 1.8 * cm, KAGGLE_URL)
        c.setFillColor(colors.black)

        c.save()
        pdf.seek(0)
        return send_file(pdf, mimetype="application/pdf", download_name="forecast_report.pdf", as_attachment=True)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
