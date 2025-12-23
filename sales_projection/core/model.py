from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
from xgboost import XGBRegressor


@dataclass
class TrainedModel:
    model: XGBRegressor
    feature_cols: list[str]


def train_xgb(X, y, xgb_params: dict) -> XGBRegressor:
    model = XGBRegressor(**xgb_params)
    model.fit(X, y)
    return model


def save_trained_model(path: str, trained: TrainedModel) -> None:
    joblib.dump({"model": trained.model, "feature_cols": trained.feature_cols}, path)


def load_trained_model(path: str) -> TrainedModel:
    obj = joblib.load(path)
    return TrainedModel(model=obj["model"], feature_cols=list(obj["feature_cols"]))


def predict_one(model: XGBRegressor, X_row: np.ndarray) -> float:
    pred = model.predict(X_row.reshape(1, -1))[0]
    return float(pred)
