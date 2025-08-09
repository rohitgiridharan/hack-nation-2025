import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import joblib


DEFAULT_DATA_PATH = str(Path(__file__).resolve().parents[1] / "data" / "sales.csv")
DEFAULT_MODEL_PATH = str(
    Path(__file__).resolve().parents[1] / "models" / "linear_regression.joblib"
)
DEFAULT_REPORT_PATH = str(
    Path(__file__).resolve().parents[1] / "reports" / "linear_metrics.json"
)


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date_ordered"])  # type: ignore[arg-type]
    # Ensure expected columns exist
    required = [
        "product_type",
        "customer_type",
        "price",
        "competitor_price",
        "promotion_flag",
        "marketing_spend",
        "economic_index",
        "seasonality_index",
        "trend_index",
        "day_of_week",
        "month",
        "price_gap",
        "quantity",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")
    return df


def build_pipeline(categorical_features, numeric_features) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", drop="first"),
                categorical_features,
            ),
            ("numeric", StandardScaler(), numeric_features),
        ]
    )

    model = Ridge(alpha=1.0, random_state=0)

    pipeline = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", model),
        ]
    )
    return pipeline


def evaluate(y_true: np.ndarray, y_pred: np.ndarray):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return {"rmse": rmse, "mae": mae, "r2": r2}


def extract_feature_names(
    preprocessor: ColumnTransformer, categorical_features, numeric_features
):
    ohe: OneHotEncoder = preprocessor.named_transformers_["categorical"]
    ohe_names = list(ohe.get_feature_names_out(categorical_features))
    num_names = list(numeric_features)
    return ohe_names + num_names, ohe_names, num_names


def coefficients_in_original_units(pipeline: Pipeline, ohe_names, num_names):
    pre: ColumnTransformer = pipeline.named_steps["preprocess"]
    lr: Ridge = pipeline.named_steps["model"]
    coef_std = lr.coef_.ravel()
    intercept_std = float(lr.intercept_)

    # Split coefficients into OHE and numeric parts (order matches ColumnTransformer)
    n_ohe = len(ohe_names)
    beta_ohe = coef_std[:n_ohe]
    beta_num_std = coef_std[n_ohe:]

    scaler: StandardScaler = pre.named_transformers_["numeric"]
    means = scaler.mean_
    scales = scaler.scale_
    scales_safe = np.where(scales == 0, 1.0, scales)

    # Transform numeric coefficients and intercept back to original feature units
    beta_num_orig = beta_num_std / scales_safe
    intercept_orig = intercept_std - float(np.sum(beta_num_std * (means / scales_safe)))

    names_all = list(ohe_names) + list(num_names)
    coefs_orig = list(beta_ohe) + list(beta_num_orig)

    coef_map_orig = {name: float(val) for name, val in zip(names_all, coefs_orig)}
    coef_map_std = {
        name: float(val)
        for name, val in zip(names_all, list(beta_ohe) + list(beta_num_std))
    }

    return intercept_orig, coef_map_orig, coef_map_std


def print_linear_equation(intercept_orig: float, coef_map_orig: dict):
    parts = [f"{intercept_orig:.4f}"]
    for name, val in coef_map_orig.items():
        sign = "+" if val >= 0 else "-"
        parts.append(f" {sign} {abs(val):.4f}*{name}")
    eq = "quantity = " + "".join(parts)
    print("Linear equation (original units):")
    print(eq)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train a linear regression model to predict quantity sold"
    )
    parser.add_argument(
        "--data", type=str, default=DEFAULT_DATA_PATH, help="Path to dataset CSV"
    )
    parser.add_argument(
        "--model-out",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help="Where to save the fitted model",
    )
    parser.add_argument(
        "--report-out",
        type=str,
        default=DEFAULT_REPORT_PATH,
        help="Where to save JSON metrics report",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data for test set (time-aware split)",
    )
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()

    df = load_data(args.data)
    df = df.sort_values("date_ordered").reset_index(drop=True)

    # Time-aware split: last N% as test
    n = len(df)
    split_idx = int(n * (1 - args.test_size))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    target = "quantity"

    categorical_features = [
        "product_type",
        "customer_type",
        "day_of_week",
        "month",
    ]

    numeric_features = [
        "price",
        "competitor_price",
        "promotion_flag",
        "marketing_spend",
        "economic_index",
        "seasonality_index",
        "trend_index",
    ]

    X_train = train_df[categorical_features + numeric_features]
    y_train = train_df[target]

    X_test = test_df[categorical_features + numeric_features]
    y_test = test_df[target]

    pipeline = build_pipeline(categorical_features, numeric_features)
    pipeline.fit(X_train, y_train)

    preds = pipeline.predict(X_test)
    metrics = evaluate(y_test.values, preds)

    # Save model
    model_out = Path(args.model_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_out)

    # Save report
    report_out = Path(args.report_out)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    with open(report_out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "num_train": int(len(train_df)),
                "num_test": int(len(test_df)),
                "metrics": metrics,
                "features": {
                    "categorical": categorical_features,
                    "numeric": numeric_features,
                },
            },
            f,
            indent=2,
        )

    # Print and save coefficients analysis
    pre = pipeline.named_steps["preprocess"]
    names_all, ohe_names, num_names = extract_feature_names(
        pre, categorical_features, numeric_features
    )
    intercept_orig, coef_map_orig, coef_map_std = coefficients_in_original_units(
        pipeline, ohe_names, num_names
    )
    print_linear_equation(intercept_orig, coef_map_orig)

    coef_report_path = report_out.with_name("linear_coefficients.json")
    with open(coef_report_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "intercept_original_units": intercept_orig,
                "coefficients_original_units": coef_map_orig,
                "coefficients_standardized": coef_map_std,
            },
            f,
            indent=2,
        )
    print(f"Saved coefficients to {coef_report_path}")

    print("Evaluation metrics (test):")
    print(json.dumps(metrics, indent=2))
    print(f"Saved model to {model_out}")
    print(f"Saved metrics report to {report_out}")


if __name__ == "__main__":
    main()
