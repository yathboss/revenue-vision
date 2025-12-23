🚀 Revenue-Vision

Production-Grade Sales Forecasting Platform

Revenue-Vision is an end-to-end sales forecasting web application built using XGBoost, Flask, and time-series machine learning.
It enables businesses and analysts to generate weekly, monthly, and yearly revenue forecasts, analyze trends, and derive actionable insights through an interactive web interface.

🔍 Key Highlights

📈 Multi-scale forecasting (Weekly / Monthly / Yearly)

🧠 Machine Learning–based predictions using XGBoost

⚡ Recursive multi-step time-series forecasting

🎛 Dynamic filtering (Category, Region, Segment)

📊 KPIs, seasonality insights & anomaly detection

📄 Export results as CSV and PDF reports

🌐 Clean, modern Flask web dashboard

🗂 Intelligent caching for fast responses

🧠 Machine Learning Approach

Revenue-Vision uses a supervised time-series learning strategy:

Data Aggregation

Raw sales data is aggregated based on selected frequency:

Weekly

Monthly

Yearly

Feature Engineering

Lag features (previous periods)

Rolling statistics (moving averages, trends)

Temporal alignment to ensure consistent time steps

Model

XGBoost Regressor

Trained on historical lag-based features

Recursive forecasting used for multi-step prediction

Forecasting Strategy

Predicts future values one step at a time

Each prediction feeds into the next step

Ensures realistic long-horizon forecasts

📊 What the Platform Shows
KPIs

Last N periods actual revenue

Next N periods forecasted revenue

Growth percentage

Insights Engine

Best predicted future period

Seasonality detection (e.g. Nov–Dec peaks)

Anomaly checks on recent performance

Auto-generated business recommendations

🏗 Project Architecture
revenue-vision/
│
├── sales_projection/
│   ├── app.py                # Flask application entry point
│   ├── config.py             # App & cache configuration
│   ├── core/
│   │   ├── data_loader.py    # Data ingestion & filters
│   │   ├── features.py       # Lag & rolling feature engineering
│   │   ├── model.py          # XGBoost training logic
│   │   ├── forecasting.py   # Recursive forecasting engine
│   │   ├── insights.py       # KPIs, seasonality, anomaly logic
│   │   ├── service.py        # Orchestration layer
│   │   └── cache.py          # Result caching
│   │
│   ├── web/
│   │   ├── templates/        # HTML templates
│   │   ├── static/           # CSS & JS
│   │
│   ├── requirements.txt
│   └── README.md
│
└── .gitignore

🌐 Web Features

Landing page with project overview

Wizard-based forecast selection

Interactive charts (Actual vs Forecast)

Dark / Light theme toggle

Downloadable CSV & PDF forecast reports

🔌 API Endpoints
Endpoint	Description
/forecast	Generate forecast JSON
/download	Download forecast as CSV
/report.pdf	Download full PDF report
⚙️ How to Run Locally
1️⃣ Clone the Repository
git clone https://github.com/yathboss/revenue-vision.git
cd revenue-vision

2️⃣ Create Virtual Environment
python -m venv venv
venv\Scripts\activate   # Windows

3️⃣ Install Dependencies
pip install -r sales_projection/requirements.txt

4️⃣ Run the App
python sales_projection/app.py


Open browser at:
👉 http://127.0.0.1:5000

🎯 Real-World Use Cases

Retail sales forecasting

Revenue planning & budgeting

Seasonal demand analysis

Short-term vs long-term growth comparison

Decision support for marketing & inventory teams

💼 Interview Talking Points

You can confidently discuss:

Time-series forecasting without ARIMA

Recursive multi-step prediction

Feature engineering for temporal data

Model vs system performance

Production concerns: caching, serialization, APIs

Full-stack ML deployment using Flask

📸 Screenshots

Add screenshots of:

Dashboard (Actual vs Forecast)

Weekly vs Monthly views

KPI cards

PDF report preview

⭐ Project Status

Completed – Production Ready

Future enhancements:

Confidence intervals

Model comparison (Prophet / LSTM)

User authentication

Cloud deployment (AWS / GCP)

👤 Author

Yatharth
Machine Learning & Full-Stack Enthusiast
