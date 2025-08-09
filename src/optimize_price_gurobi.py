import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import gurobipy as gp
    from gurobipy import GRB
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "gurobipy is required. Please install Gurobi and ensure a valid license is available."
    ) from e


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Simple price optimization with Gurobi using isoelastic demand.\n"
            "We maximize profit = ((1 - r) * p - c0) * A * p^{-E} with A from your baseline.\n"
            "Inputs are inferred from the CSV; only --data is required."
        )
    )
    p.add_argument(
        "--data",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "data" / "sales.csv"),
        help="Path to CSV (default: data/sales.csv)",
    )
    p.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "reports" / "price_opt_per_row.csv"),
        help="Path to write per-row CSV result (default: reports/price_opt_per_row.csv)",
    )
    return p.parse_args()


def _solve_row_with_gurobi(p0: float, q: float, E: float, r: float, c0: float) -> dict:
    if not (p0 > 0 and q > 0 and E > 0 and 0 <= r < 1 and c0 >= 0):
        raise ValueError("Invalid inputs for row optimization.")

    # Demand scale and price bounds per row
    A = float(q * (p0 ** E)) # sets the isoelastic demand scale so the curve passes through the baseline (p0, q). p0=initial_price, q=quantity
    pmin = max(1e-4, 0.2 * p0) # 20% below baseline
    pmax = 2.5 * p0 # 250% above baseline

    m = gp.Model("row_price_opt")
    m.Params.NonConvex = 2
    m.Params.OutputFlag = 0

    # Decision vars and bounds
    p = m.addVar(lb=pmin, ub=pmax, name="price")
    # z = p^{-E}; monotone bounds: z in [pmax^{-E}, pmin^{-E}]
    z = m.addVar(lb=(pmax ** (-E)), ub=(pmin ** (-E)), name="p_pow_minus_E")

    # Link z and p with a single power constraint so demand can be expressed in the objective.
    m.addGenConstrPow(z, p, -E, name="pow_neg")

    # Objective: maximize profit
    # Why z is used: z = p^(−E) lets the solver handle the power relation via a single constraint. Then profit is a simple product of (linear in p) and z. 
    m.setObjective(A * ((p - r*p) - c0) * z, GRB.MAXIMIZE)
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Gurobi status {m.Status} for row optimization")

    return {
        "optimal_price": float(p.X),
        "optimal_quantity": float(A * (p.X ** (-E))),
        "unit_margin": float((1.0 - r) * p.X - c0),
        "total_profit": float(A * (((1.0 - r) * p.X) - c0) * (p.X ** (-E))),
        "A": A,
        "elasticity": E,
        "ad_valorem_rate": r,
        "per_unit_cost": c0,
        "pmin": pmin,
        "pmax": pmax,
    }


def main():
    args = parse_args()

    # 1) Load CSV
    df = pd.read_csv(args.data)
    df = df.head(10)
    if len(df) == 0:
        raise ValueError("CSV is empty; cannot infer inputs.")

    # 2) Infer baselines and parameters from CSV (robust stats)
    #    Baseline price p0 from median price
    if "price" not in df.columns:
        raise ValueError("CSV missing required column 'price'.")
    p0 = float(pd.to_numeric(df["price"], errors="coerce").dropna().median())
    if not np.isfinite(p0) or p0 <= 0:
        raise ValueError("Invalid baseline price derived from CSV.")

    #    Baseline quantity q0: prefer predicted_quantity else quantity
    qty_col = "predicted_quantity" if "predicted_quantity" in df.columns else "quantity"
    if qty_col not in df.columns:
        raise ValueError("CSV must include 'quantity' or 'predicted_quantity'.")
    q0 = float(pd.to_numeric(df[qty_col], errors="coerce").dropna().mean())
    if not np.isfinite(q0) or q0 <= 0:
        raise ValueError("Invalid baseline quantity derived from CSV.")

    #    Elasticity magnitude E from price_elasticity
    if "price_elasticity" not in df.columns:
        raise ValueError("CSV missing required column 'price_elasticity'.")
    E = float(pd.to_numeric(df["price_elasticity"], errors="coerce").dropna().median())
    if not np.isfinite(E) or E <= 0:
        raise ValueError("Invalid elasticity derived from CSV.")

    #    Costs: ad valorem r and per-unit c0 (use 0 if columns absent)
    if "ad_valorem_rate" in df.columns:
        r = float(pd.to_numeric(df["ad_valorem_rate"], errors="coerce").dropna().median())
    else:
        r = 0.0
    if not (0 <= r < 1):
        raise ValueError("Invalid 'ad_valorem_rate' derived from CSV; must be in [0,1).")

    if "per_unit_cost" in df.columns:
        c0 = float(pd.to_numeric(df["per_unit_cost"], errors="coerce").dropna().mean())
    else:
        c0 = 0.0
    if not np.isfinite(c0) or c0 < 0:
        raise ValueError("Invalid per-unit cost derived from CSV.")

    # 3) Solve per row using row-specific baselines and parameters
    #    We derive row-level p0, q0, E, r, c0 from that row; if r/c0 missing, use 0.
    results = []
    price_series = pd.to_numeric(df["price"], errors="coerce")
    qty_series = (
        pd.to_numeric(df["predicted_quantity"], errors="coerce")
        if "predicted_quantity" in df.columns
        else pd.to_numeric(df["quantity"], errors="coerce")
    )
    E_series = pd.to_numeric(df["price_elasticity"], errors="coerce")
    r_series = pd.to_numeric(df.get("ad_valorem_rate", pd.Series([np.nan] * len(df))), errors="coerce")
    c0_series = pd.to_numeric(df.get("per_unit_cost", pd.Series([np.nan] * len(df))), errors="coerce")

    for idx in range(len(df)):
        p0_i = float(price_series.iloc[idx]) if np.isfinite(price_series.iloc[idx]) else np.nan
        q0_i = float(qty_series.iloc[idx]) if np.isfinite(qty_series.iloc[idx]) else np.nan
        E_i = float(E_series.iloc[idx]) if np.isfinite(E_series.iloc[idx]) else np.nan
        r_i = float(r_series.iloc[idx]) if np.isfinite(r_series.iloc[idx]) else 0.0
        c0_i = float(c0_series.iloc[idx]) if np.isfinite(c0_series.iloc[idx]) else 0.0

        if not (np.isfinite(p0_i) and np.isfinite(q0_i) and np.isfinite(E_i)):
            # Skip row with insufficient inputs
            results.append({
                "optimal_price": np.nan,
                "optimal_quantity": np.nan,
                "unit_margin": np.nan,
                "total_profit": np.nan,
            })
            continue

        try:
            sol = _solve_row_with_gurobi(p0=p0_i, q0=q0_i, E=E_i, r=r_i, c0=c0_i)
            results.append({
                "optimal_price": sol["optimal_price"],
                "optimal_quantity": sol["optimal_quantity"],
                "unit_margin": sol["unit_margin"],
                "total_profit": sol["total_profit"],
            })
        except Exception:
            results.append({
                "optimal_price": np.nan,
                "optimal_quantity": np.nan,
                "unit_margin": np.nan,
                "total_profit": np.nan,
            })

    # 4) Write per-row results merged with original data
    res_df = pd.DataFrame(results)
    out_df = pd.concat([df.reset_index(drop=True), res_df], axis=1)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)

    print(f"Wrote per-row optimal prices to {out_path} ({len(out_df)} rows)")


if __name__ == "__main__":
    main()


