from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "superstore.csv"

STORAGE_DIR = BASE_DIR / "storage"
MODELS_DIR = STORAGE_DIR / "models"
CACHE_DIR = STORAGE_DIR / "cache"
PRECOMPUTED_DIR = STORAGE_DIR / "precomputed"

HORIZON = {
    "weekly": 13,
    "monthly": 12,
    "yearly": 12,
}

# Reasonable defaults for tabular time-series features
XGB_PARAMS = {
    "n_estimators": 250,
    "learning_rate": 0.05,
    "max_depth": 5,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "n_jobs": 4,
    "tree_method": "hist",
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "random_state": 42,
    "objective": "reg:squarederror",
}

# We keep the last K points as validation when training in advanced mode
DEFAULT_VALIDATION_POINTS = {
    "weekly": 13,
    "monthly": 6,
    "yearly": 6,
}
