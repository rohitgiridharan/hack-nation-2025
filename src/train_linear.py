import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
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
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features,
            ),
            ("numeric", StandardScaler(), numeric_features),
        ]
    )

    model = LinearRegression()

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
        "price_gap",
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

    print("Evaluation metrics (test):")
    print(json.dumps(metrics, indent=2))
    print(f"Saved model to {model_out}")
    print(f"Saved metrics report to {report_out}")

    print("====================test======================")
    # Example input data structure
    single_input = {
        "product_type": "Diagnostic Kit",
        "customer_type": "Pharmaceutical Company",
        "day_of_week": "Sunday",
        "month": "May",
        "price": 189.39,
        "competitor_price": 195.37,
        "price_gap": 0,
        "promotion_flag": 114706.97,
        "marketing_spend": -0.23347217569720005,
        "economic_index": 0.10490381056766582,
        "seasonality_index": 0.9358974358974359,
        "trend_index": 6
    }


    # OR load from JSON file
    # with open(input_data_path, "r") as f:
    #     single_input = json.load(f)

    # Convert to DataFrame
    input_df = pd.DataFrame([single_input])

    # === 3. Predict ===
    predicted_quantity = pipeline.predict(input_df)[0]

    # === 4. Output result ===
    print(f"Predicted quantity: {predicted_quantity:.2f}")



if __name__ == "__main__":
    main()
