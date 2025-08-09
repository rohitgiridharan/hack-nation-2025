import argparse
import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

# Default base prices, used to compute price_gap if base price not provided
DEFAULT_BASE_PRICE = {
    "Diagnostic Kit": 180.0,
    "Reagent": 75.0,
    "Instrument": 2500.0,
    "Consumable": 30.0,
    "Assay Panel": 400.0,
}


def compute_seasonality_index(month: int) -> float:
    # Same formulation as generator
    return 0.15 * np.sin(2 * np.pi * (month - 1) / 12) + 0.05 * np.cos(
        2 * np.pi * (month - 1) / 12
    )


def build_feature_row(
    product_type: str,
    customer_type: str,
    price: float,
    competitor_price: float,
    base_price: float,
    promotion_flag: int,
    marketing_spend: float,
    economic_index: float,
    month: int,
    day_of_week: int,
    trend_index: float,
) -> pd.DataFrame:
    seasonality_index = compute_seasonality_index(month)
    price_gap = (competitor_price - price) / base_price

    row = {
        "product_type": product_type,
        "customer_type": customer_type,
        "price": float(price),
        "competitor_price": float(competitor_price),
        "price_gap": float(price_gap),
        "promotion_flag": int(promotion_flag),
        "marketing_spend": float(marketing_spend),
        "economic_index": float(economic_index),
        "seasonality_index": float(seasonality_index),
        "trend_index": float(trend_index),
        "day_of_week": int(day_of_week),
        "month": int(month),
    }
    return pd.DataFrame([row])


def clamp_quantity(q: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, q)


def optimize_price(
    model_path: Path,
    product_type: str,
    customer_type: str,
    competitor_price: float,
    unit_cost: float,
    promotion_flag: int = 0,
    marketing_spend: float = 80_000.0,
    economic_index: float = 0.0,
    month: Optional[int] = None,
    day_of_week: Optional[int] = None,
    trend_index: float = 0.5,
    base_price: Optional[float] = None,
    min_price: float = 1.0,
    max_price: float = 5000.0,
    num_points: int = 200,
) -> dict:
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. Train the model first."
        )

    pipeline = joblib.load(model_path)

    # Defaults for calendar
    if month is None:
        month = 6
    if day_of_week is None:
        day_of_week = 2  # Wednesday

    # Determine base price for price_gap normalization
    if base_price is None:
        base_price = float(
            DEFAULT_BASE_PRICE.get(product_type, max(1.0, competitor_price))
        )

    # Create grid of candidate prices
    grid = np.linspace(min_price, max_price, num_points)

    profits = []
    quantities = []

    for p in grid:
        features = build_feature_row(
            product_type=product_type,
            customer_type=customer_type,
            price=float(p),
            competitor_price=float(competitor_price),
            base_price=float(base_price),
            promotion_flag=int(promotion_flag),
            marketing_spend=float(marketing_spend),
            economic_index=float(economic_index),
            month=int(month),
            day_of_week=int(day_of_week),
            trend_index=float(trend_index),
        )
        pred_qty = float(pipeline.predict(features)[0])
        pred_qty = float(max(0.0, pred_qty))
        profit = (p - unit_cost) * pred_qty
        profits.append(profit)
        quantities.append(pred_qty)

    profits = np.array(profits)
    quantities = np.array(quantities)

    best_idx = int(np.argmax(profits))

    result = {
        "recommended_price": float(grid[best_idx]),
        "expected_quantity": float(quantities[best_idx]),
        "expected_profit": float(profits[best_idx]),
        "price_grid_min": float(grid.min()),
        "price_grid_max": float(grid.max()),
        "num_grid_points": int(num_points),
    }
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Find profit-maximizing price using the trained linear model"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(
            Path(__file__).resolve().parents[1] / "models" / "linear_regression.joblib"
        ),
    )

    # Required business inputs
    parser.add_argument("--product-type", type=str, required=True)
    parser.add_argument("--customer-type", type=str, required=True)
    parser.add_argument("--competitor-price", type=float, required=True)
    parser.add_argument(
        "--unit-cost", type=float, required=True, help="Unit variable cost for the SKU"
    )

    # Optional scenario inputs
    parser.add_argument("--promotion-flag", type=int, default=0, choices=[0, 1])
    parser.add_argument("--marketing-spend", type=float, default=80_000.0)
    parser.add_argument("--economic-index", type=float, default=0.0)
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--day-of-week", type=int, default=None)
    parser.add_argument("--trend-index", type=float, default=0.5)
    parser.add_argument(
        "--base-price",
        type=float,
        default=None,
        help="Baseline list price used to compute price_gap; if omitted uses a default per product type",
    )

    # Search space
    parser.add_argument("--min-price", type=float, default=1.0)
    parser.add_argument("--max-price", type=float, default=5000.0)
    parser.add_argument("--num-points", type=int, default=200)

    # Output
    parser.add_argument(
        "--out", type=str, default=None, help="Optional JSON output path"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    result = optimize_price(
        model_path=Path(args.model),
        product_type=args.product_type,
        customer_type=args.customer_type,
        competitor_price=args.competitor_price,
        unit_cost=args.unit_cost,
        promotion_flag=args.promotion_flag,
        marketing_spend=args.marketing_spend,
        economic_index=args.economic_index,
        month=args.month,
        day_of_week=args.day_of_week,
        trend_index=args.trend_index,
        base_price=args.base_price,
        min_price=args.min_price,
        max_price=args.max_price,
        num_points=args.num_points,
    )

    print(json.dumps(result, indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
