# Life Sciences Sales Quantity Prediction

Quickstart:

1. Create/activate a Python 3.10+ environment and install dependencies:

```
pip install -r requirements.txt
```

2. Generate a synthetic dataset (50k rows over 18 months by default):

```
python src/generate_data.py --rows 50000 --start-date 2023-01-01 --months 18 --seed 42 --out data/sales.csv
```

3. Train a linear regression model and evaluate:

```
python src/train_linear.py --data data/sales.csv --model-out models/linear_regression.joblib --report-out reports/linear_metrics.json
```

Files:
- `src/generate_data.py`: synthetic data generator with seasonality, marketing spend, macro index, pricing, and events.
- `src/train_linear.py`: preprocessing + linear model training, time-aware split, metrics, and model saving.

4. Optional: Add price elasticity feature to the generated dataset:

```
python src/postprocess_add_elasticity.py --in data/sales.csv --out data/sales_with_elasticity.csv --group-cols product_type,customer_type --min-samples 100 --clip -5.0,1.0
```

This estimates a log-log slope of quantity vs. price within each segment (default: by `product_type` and `customer_type`) and adds it as `price_elasticity`. Values are clipped to [-5, 1] to avoid unstable extremes.
