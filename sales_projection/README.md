# Sales Projection (Flask + XGBoost)

A web-based sales forecasting SaaS-style demo using the Superstore dataset.

## Features
- Forecast frequency: **Weekly**, **Monthly**, **Yearly** (yearly = next 12 months forecast)
- Filters: Category / Region / Segment (or All)
- Hybrid mode:
  - **Fast**: precomputed store + caching
  - **Advanced**: compute on demand (cached after first run)
- Results:
  - Actual vs Forecast line chart
  - KPI cards (last 3 months actual, next 3 months forecast, growth %)
  - Insights (best period, seasonality, anomaly warning)
  - Forecast table + CSV download
  - Year-wise totals (past + predicted)

## Run locally
```bash
cd sales_projection
python app.py
```
Open: http://localhost:5000

## API
Example:
```
/forecast?freq=monthly&category=All&region=West&segment=Consumer&mode=fast
```

## Model summary
- XGBoost regressor
- Lag features + rolling stats + calendar & seasonality features
- Recursive multi-step forecasting
