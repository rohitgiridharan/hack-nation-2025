import argparse
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from pathlib import Path


PRODUCT_TYPES = [
    "Diagnostic Kit",
    "Reagent",
    "Instrument",
    "Consumable",
    "Assay Panel",
]

CUSTOMER_TYPES = [
    "Pharmaceutical Company",
    "Academia",
    "Biotech Startup",
]

PRODUCT_BASE_PRICE = {
    "Diagnostic Kit": 180.0,
    "Reagent": 75.0,
    "Instrument": 2500.0,
    "Consumable": 30.0,
    "Assay Panel": 400.0,
}

# Average base demand contribution by product type and customer type
PRODUCT_BASE_DEMAND = {
    "Diagnostic Kit": 22.0,
    "Reagent": 26.0,
    "Instrument": 6.0,
    "Consumable": 32.0,
    "Assay Panel": 14.0,
}

CUSTOMER_BASE_DEMAND = {
    "Pharmaceutical Company": 14.0,
    "Academia": 9.0,
    "Biotech Startup": 7.0,
}


def month_sin(month: int) -> float:
    # month: 1-12 inclusive
    return np.sin(2 * np.pi * (month - 1) / 12)


def month_cos(month: int) -> float:
    return np.cos(2 * np.pi * (month - 1) / 12)


def dow_sin(dow: int) -> float:
    # Monday=0 .. Sunday=6
    return np.sin(2 * np.pi * dow / 7)


def dow_cos(dow: int) -> float:
    return np.cos(2 * np.pi * dow / 7)


def generate_monthly_series(
    start_date: pd.Timestamp, end_date: pd.Timestamp, rng: np.random.Generator
):
    months = pd.period_range(start=start_date, end=end_date, freq="M").to_timestamp()
    num_months = len(months)

    # Marketing spend: baseline with seasonal lift and noise
    base_marketing = rng.uniform(50_000, 120_000, size=num_months)
    seasonal = 1.0 + 0.25 * np.sin(2 * np.pi * np.arange(num_months) / 12)
    marketing_spend = base_marketing * seasonal * rng.normal(1.0, 0.10, size=num_months)

    # Economic index: slow-moving trend plus noise, normalized ~ N(0, 1)
    trend = np.linspace(-0.5, 0.5, num_months)
    econ_raw = trend + rng.normal(0.0, 0.35, size=num_months)
    econ_idx = (econ_raw - np.mean(econ_raw)) / (np.std(econ_raw) + 1e-8)

    # Competitor launch month (once) and regulatory event month (maybe once)
    comp_launch_month = (
        months[rng.integers(low=0, high=num_months)] if num_months > 3 else None
    )
    regulatory_month = (
        months[rng.integers(low=0, high=num_months)]
        if rng.random() < 0.8 and num_months > 3
        else None
    )

    return months, marketing_spend, econ_idx, comp_launch_month, regulatory_month


def generate_rows(n_rows: int, start_date: str, months: int, seed: int, out_path: Path):
    rng = np.random.default_rng(seed)
    start_ts = pd.to_datetime(start_date)
    end_ts = start_ts + pd.DateOffset(months=months) - pd.DateOffset(days=1)

    monthly_ts, marketing_spend_m, econ_idx_m, comp_launch_m, regulatory_m = (
        generate_monthly_series(start_ts, end_ts, rng)
    )
    month_to_marketing = dict(zip(monthly_ts.month, marketing_spend_m))
    month_to_econ = dict(zip(monthly_ts.month, econ_idx_m))

    # Pre-sample dates uniformly then add weekday weighting (Mon-Thu > Fri > Weekend)
    dates = start_ts + (end_ts - start_ts) * rng.random(n_rows)
    dates = pd.Series(pd.to_datetime(dates).floor("D"))

    # Apply simple weekday weighting by resampling a fraction
    weekday_weights = {0: 1.2, 1: 1.2, 2: 1.2, 3: 1.2, 4: 1.0, 5: 0.6, 6: 0.6}
    probs = np.array([weekday_weights[d.weekday()] for d in dates], dtype=float)
    probs /= probs.sum()
    idx = rng.choice(np.arange(n_rows), size=n_rows, replace=True, p=probs)
    dates = dates.iloc[idx].reset_index(drop=True)

    # Pre-allocate
    records = []

    for i in range(n_rows):
        ts = dates.iloc[i]
        month = int(ts.month)
        dow = int(ts.weekday())  # Monday=0

        product = rng.choice(PRODUCT_TYPES, p=[0.22, 0.28, 0.08, 0.30, 0.12])
        customer = rng.choice(CUSTOMER_TYPES, p=[0.5, 0.3, 0.2])

        base_price = PRODUCT_BASE_PRICE[product]
        # Promotion may discount price by 5-20%
        promotion = 1 if rng.random() < 0.22 else 0
        discount = rng.uniform(0.05, 0.20) if promotion else 0.0
        # Realized price around base, with multiplicative noise and optional discount
        price = base_price * rng.lognormal(mean=0.0, sigma=0.05) * (1.0 - discount)

        # Competitor price typically slightly higher but noisy
        competitor_price = base_price * rng.lognormal(mean=0.03, sigma=0.07)

        # Marketing and macro signals by month
        marketing_spend = month_to_marketing.get(
            month, float(np.mean(list(month_to_marketing.values())))
        )
        econ_idx = month_to_econ.get(month, 0.0)

        # Seasonality
        seasonality_index = 0.15 * month_sin(month) + 0.05 * month_cos(month)

        # Time trend from 0 to 1 across the full window
        trend_index = (ts - start_ts).days / max(1, (end_ts - start_ts).days)

        # Events
        competitor_launch_flag = 0
        regulatory_event_flag = 0
        if comp_launch_m is not None and ts >= comp_launch_m:
            # Instruments and Assay Panels more impacted by competitor launch
            competitor_launch_flag = (
                1
                if product in ("Instrument", "Assay Panel")
                else (1 if rng.random() < 0.35 else 0)
            )
        if (
            regulatory_m is not None
            and ts.month == regulatory_m.month
            and ts.year == regulatory_m.year
        ):
            regulatory_event_flag = 1 if rng.random() < 0.6 else 0

        # Price gap relative to product base
        price_gap = (competitor_price - price) / base_price
        effective_price_delta = (price / base_price) - 1.0

        # Baselines
        base_demand = PRODUCT_BASE_DEMAND[product] + CUSTOMER_BASE_DEMAND[customer]

        # Demand model (linear with noise), calibrated to produce positive integer-ish quantities
        quantity = (
            15.0
            + base_demand
            + 22.0 * seasonality_index
            + 14.0 * np.log1p(marketing_spend / 50_000.0)
            + 18.0 * price_gap
            - 28.0 * effective_price_delta
            + 8.0 * promotion
            + 10.0 * econ_idx
            + 12.0 * trend_index
            - 6.0 * (1 if dow >= 5 else 0)  # weekends lower
            - 5.0 * competitor_launch_flag
            + 6.0 * regulatory_event_flag
            + rng.normal(0.0, 4.0)
        )

        quantity = max(0.0, quantity)
        quantity = float(np.round(quantity, 0))

        records.append(
            {
                "order_id": f"ORD-{i:07d}",
                "date_ordered": ts.date().isoformat(),
                "product_type": product,
                "customer_type": customer,
                "price": round(float(price), 2),
                "competitor_price": round(float(competitor_price), 2),
                "promotion_flag": promotion,
                "marketing_spend": round(float(marketing_spend), 2),
                "economic_index": float(econ_idx),
                "seasonality_index": float(seasonality_index),
                "trend_index": float(trend_index),
                "day_of_week": dow,
                "month": month,
                "price_gap": float(price_gap),
                "quantity": int(quantity),
            }
        )

    df = pd.DataFrame.from_records(records)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    meta = {
        "n_rows": n_rows,
        "start_date": start_date,
        "end_date": end_ts.date().isoformat(),
        "seed": seed,
        "product_types": PRODUCT_TYPES,
        "customer_types": CUSTOMER_TYPES,
    }
    with open(out_path.with_suffix(".meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return df


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic life sciences sales dataset"
    )
    parser.add_argument(
        "--rows", type=int, default=50000, help="Number of rows to generate"
    )
    parser.add_argument(
        "--start-date", type=str, default="2023-01-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--months", type=int, default=18, help="Number of months from start-date"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data" / "sales.csv"),
        help="Output CSV path",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    out_path = Path(args.out)
    generate_rows(
        n_rows=args.rows,
        start_date=args.start_date,
        months=args.months,
        seed=args.seed,
        out_path=out_path,
    )
    print(f"Wrote dataset to {out_path}")


if __name__ == "__main__":
    main()
