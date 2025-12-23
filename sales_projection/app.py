from __future__ import annotations

import io
from datetime import datetime, datetime as dt
from dataclasses import asdict, is_dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from flask import Flask, jsonify, render_template, request, send_file, Response
from flask.json.provider import DefaultJSONProvider

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from sales_projection.config import CACHE_DIR
from sales_projection.core.forecasting import recursive_forecast
from sales_projection.core.service import run_forecast


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
    import pandas as pd

    # 1) Load data
    try:
        from sales_projection.core.data_loader import load_superstore_data
        df = load_superstore_data()
    except Exception:
        data_path = Path(__file__).resolve().parent / "data" / "superstore.csv"
        if data_path.exists():
            df = pd.read_csv(data_path)
        else:
            df = pd.read_csv("sales_projection/data/superstore.csv")

    # 2) Date + Sales columns
    if "Order Date" in df.columns:
        df["Order Date"] = pd.to_datetime(df["Order Date"])
        date_col = "Order Date"
    elif "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"])
        date_col = "order_date"
    else:
        date_candidates = [c for c in df.columns if "date" in c.lower()]
        if not date_candidates:
            raise ValueError("No date column found in dataset.")
        date_col = date_candidates[0]
        df[date_col] = pd.to_datetime(df[date_col])

    if "Sales" in df.columns:
        sales_col = "Sales"
    elif "sales" in df.columns:
        sales_col = "sales"
    else:
        raise ValueError("Sales column not found in dataset.")

    # 3) Filters
    def apply_filter(col, val):
        nonlocal df
        if val and val != "All" and col in df.columns:
            df = df[df[col] == val]

    apply_filter("Category", params.get("category", "All"))
    apply_filter("Region", params.get("region", "All"))
    apply_filter("Segment", params.get("segment", "All"))

    if df.empty:
        raise ValueError("No data found for selected filters. Try selecting All.")

    # 4) Frequency + horizon
    freq = (params.get("freq") or "monthly").lower()
    if freq == "weekly":
        rule = "W"
        horizon = 13
    elif freq == "yearly":
        # yearly = next 12 months (monthly points)
        rule = "MS"
        horizon = 12
    else:
        rule = "MS"
        horizon = 12

    series_df = (
        df.set_index(date_col)[sales_col]
        .resample(rule)
        .sum()
        .reset_index()
        .rename(columns={date_col: "ds", sales_col: "y"})
        .sort_values("ds")
        .dropna()
    )

    if len(series_df) < 6:
        raise ValueError("Not enough history for forecast. Try broader filters or All.")

    # 5) XGB params
    try:
        from sales_projection.core.model import DEFAULT_XGB_PARAMS
        xgb_params = DEFAULT_XGB_PARAMS
    except Exception:
        xgb_params = {
            "n_estimators": 400,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "random_state": 42,
        }

    # 6) Forecast
    result = recursive_forecast(
        series_df=series_df,
        horizon=horizon,
        xgb_params=xgb_params,
        freq=freq,
    )

    return ensure_dict(result)


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
    import pandas as pd

    class CustomJSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, (pd.Timestamp, dt)):
                return obj.isoformat()
            return super().default(obj)

    app.json = CustomJSONProvider(app)

    @app.get("/")
    def landing():
        return render_template("landing.html", kaggle_url=KAGGLE_URL)

    @app.get("/wizard")
    def wizard():
        from sales_projection.core.data_loader import get_filter_options
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
