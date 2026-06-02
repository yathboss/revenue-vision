from __future__ import annotations

import csv
from pathlib import Path


# ---------------------------------------------------
# Load Superstore dataset (single source of truth)
# ---------------------------------------------------
def load_superstore_data() -> list[dict[str, str]]:
    data_path = Path(__file__).resolve().parents[1] / "data" / "superstore.csv"

    if not data_path.exists():
        raise FileNotFoundError(f"superstore.csv not found at: {data_path}")

    with data_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------
# Filter options for Wizard (Category / Region / Segment)
# ---------------------------------------------------
def get_filter_options() -> dict:
    rows = load_superstore_data()

    required_cols = ["Category", "Region", "Segment"]
    available = set(rows[0].keys()) if rows else set()
    missing = [c for c in required_cols if c not in available]

    if missing:
        raise ValueError(
            f"Missing columns in superstore.csv: {missing}. "
            f"Available columns: {sorted(available)}"
        )

    def uniq(col: str) -> list[str]:
        return sorted({(r.get(col) or "").strip() for r in rows if (r.get(col) or "").strip()})

    return {
        "categories": uniq("Category"),
        "regions": uniq("Region"),
        "segments": uniq("Segment"),
    }
