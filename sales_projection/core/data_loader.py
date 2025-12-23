from __future__ import annotations

from pathlib import Path
import pandas as pd


# ---------------------------------------------------
# Load Superstore dataset (single source of truth)
# ---------------------------------------------------
def load_superstore_data() -> pd.DataFrame:
    data_path = Path(__file__).resolve().parents[1] / "data" / "superstore.csv"

    if not data_path.exists():
        raise FileNotFoundError(f"superstore.csv not found at: {data_path}")

    df = pd.read_csv(data_path)
    return df


# ---------------------------------------------------
# Filter options for Wizard (Category / Region / Segment)
# ---------------------------------------------------
def get_filter_options() -> dict:
    df = load_superstore_data()

    required_cols = ["Category", "Region", "Segment"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing columns in superstore.csv: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    def uniq(col: str) -> list[str]:
        return sorted(
            df[col]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

    return {
        "categories": uniq("Category"),
        "regions": uniq("Region"),
        "segments": uniq("Segment"),
    }
