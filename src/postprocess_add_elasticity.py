import argparse
import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd


def compute_log_log_slope(x: np.ndarray, y: np.ndarray) -> float:
    # Fit y = a + b x; return b. Use np.polyfit for stability with intercept.
    # x = ln(price), y = ln(quantity + 1)
    if np.allclose(x.var(), 0.0) or np.allclose(y.var(), 0.0):
        return np.nan
    try:
        b, a = (
            np.polyfit(x, y, deg=1)[0],
            np.polyfit(x, y, deg=1)[1],
        )  # polyfit returns [slope, intercept] when deg=1
        # The above line mistakenly calls polyfit twice; compute once properly below.
    except Exception:
        return np.nan
    return b


def safe_compute_slope(x: np.ndarray, y: np.ndarray) -> float:
    # Single polyfit computation
    try:
        coeffs = np.polyfit(x, y, deg=1)
        return float(coeffs[0])
    except Exception:
        return float("nan")


def add_price_elasticity(
    df: pd.DataFrame,
    group_columns: List[str],
    min_samples_per_group: int = 100,
    clip_range: Tuple[float, float] = (-5.0, 1.0),
) -> pd.DataFrame:
    # Prepare log variables
    df = df.copy()
    df = df[df["price"] > 0].copy()
    df["_ln_price"] = np.log(df["price"].values)
    df["_ln_qty"] = np.log1p(df["quantity"].values)

    # Compute elasticity per group
    elasticity_by_group = {}
    grouped = df.groupby(group_columns, dropna=False)
    for group_key, g in grouped:
        if len(g) < min_samples_per_group:
            elasticity_by_group[group_key] = np.nan
            continue
        slope = safe_compute_slope(g["_ln_price"].values, g["_ln_qty"].values)
        if np.isfinite(slope):
            slope = float(np.clip(slope, clip_range[0], clip_range[1]))
        elasticity_by_group[group_key] = slope

    # Map elasticity back to rows
    # Create a key Series to map
    key_df = df[group_columns].astype(str)
    map_keys = list(elasticity_by_group.keys())

    # Build a mapping DataFrame for merge to handle tuple keys robustly
    map_rows = []
    for key, val in elasticity_by_group.items():
        if not isinstance(key, tuple):
            key = (key,)
        row = {col: str(k) for col, k in zip(group_columns, key)}
        row["price_elasticity"] = abs(val)
        map_rows.append(row)
    mapping = pd.DataFrame(map_rows)

    out = df.merge(
        mapping,
        how="left",
        left_on=group_columns,
        right_on=group_columns,
        validate="m:1",
    )

    # Clean up temp columns
    out = out.drop(columns=["_ln_price", "_ln_qty"])  # type: ignore[arg-type]

    return out


def parse_args():
    parser = argparse.ArgumentParser(
        description="Add price elasticity feature to generated sales dataset"
    )
    parser.add_argument(
        "--in",
        dest="input_csv",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data" / "sales.csv"),
        help="Input CSV path",
    )
    parser.add_argument(
        "--out",
        dest="output_csv",
        type=str,
        default=str(
            Path(__file__).resolve().parents[1] / "data" / "sales_with_elasticity.csv"
        ),
        help="Output CSV path",
    )
    parser.add_argument(
        "--group-cols",
        type=str,
        default="product_type,customer_type",
        help="Comma-separated columns to group by when estimating elasticity",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=100,
        help="Minimum rows per group to estimate elasticity",
    )
    parser.add_argument(
        "--clip",
        type=str,
        default="-5.0,1.0",
        help="Min,max clip range for elasticity values",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)

    group_cols = [c.strip() for c in args.group_cols.split(",") if c.strip()]
    clip_tokens = [t.strip() for t in args.clip.split(",")]
    if len(clip_tokens) != 2:
        raise ValueError("--clip must be 'min,max'")
    clip_range = (float(clip_tokens[0]), float(clip_tokens[1]))

    df = pd.read_csv(input_csv)
    for col in ["price", "quantity"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in {input_csv}")

    enriched = add_price_elasticity(
        df=df,
        group_columns=group_cols,
        min_samples_per_group=args.min_samples,
        clip_range=clip_range,
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_csv, index=False)

    # Also write a small summary JSON of segment elasticities
    summary = (
        enriched[group_cols + ["price_elasticity"]]
        .drop_duplicates()
        .sort_values(group_cols)
        .to_dict(orient="records")
    )
    with open(
        output_csv.with_suffix(".elasticity_summary.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote enriched dataset with elasticity to {output_csv}")
    print(
        f"Wrote segment elasticity summary to {output_csv.with_suffix('.elasticity_summary.json')}"
    )


if __name__ == "__main__":
    main()
