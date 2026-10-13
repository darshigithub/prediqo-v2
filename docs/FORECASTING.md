# Prediqo — Time-Series Forecasting Intelligence Layer

## 1. Architecture & Core Philosophy

Prediqo's **Time-Series Forecasting Intelligence Layer** (`backend/app/forecasting/`) provides dedicated temporal projection capabilities for business metrics over regular calendar frequencies (daily, weekly, monthly, quarterly, yearly).

### Prediction vs. Forecasting Separation

A fundamental architectural principle of Prediqo is the strict separation between **Supervised Record-Level Prediction** and **Time-Series Forecasting**:

| Attribute | Supervised Prediction (`/api/prediction/`) | Time-Series Forecasting (`/api/forecast/`) |
|---|---|---|
| **Core Question** | *"What will the target value be for this specific record?"* | *"What will the aggregate metric value be over future time periods?"* |
| **Data Nature** | Tabular feature rows $(X_i \rightarrow y_i)$ | Chronologically ordered temporal points $(t, y_t)$ |
| **Validation** | K-Fold Cross-Validation / Chronological Split | Strict Chronological Backtesting $(N - H \text{ vs } H)$ |
| **Random Shuffle** | Allowed for independent cross-sectional records | **Strictly Prohibited** (causes lookahead data leakage) |
| **Input Format** | Full feature dictionary (`Record<string, any>`) | Date column, metric, frequency, horizon step count |
| **Uncertainty** | Residual distribution & variance | Expanding horizon prediction intervals ($80\%$ & $95\% \propto \sqrt{h}$) |
| **Output Type** | Single numeric scalar or class probabilities | Chronological projection series with timestamped points |

```text
       [ Parquet Analytical Storage ]
                     |
         (DuckDB date_trunc Query)
                     v
       [ Aggregated Calendar Series ]
                     |
         (Continuous Reindexing & Imputation)
                     v
       [ Chronological Backtest Split (N - H vs H) ]
                     |
         +-----------+-----------+
         |                       |
         v                       v
 [ Candidate Forecasters ] [ Chronological Backtest ]
 (Naive, SNaive, MA, ES)   (MAE, RMSE, WAPE, zero-safe MAPE)
         |                       |
         +-----------+-----------+
                     |
                     v
             [ Best Forecaster ]
                     |
        (Project H Steps + Uncertainty Intervals)
                     v
   [ Stored Model & Future Projections (80% / 95%) ]
```

---

## 2. End-to-End Forecasting Pipeline

### Stage 1: Feasibility & Boundary Detection (`feasibility.py`)
Before training, the dataset is evaluated for forecasting eligibility:
1. **Datetime Detection**: Discovers candidate date columns matching semantic type `DATE` or temporal name patterns (`date`, `time`, `timestamp`, `purchased_on`, `created_at`).
2. **Metric Detection**: Discovers numeric aggregatable metrics (`MEASURE`) with positive variance.
3. **DuckDB Parquet Boundaries**: Executes lightweight DuckDB queries directly over Parquet to find exact chronological limits:
   ```sql
   SELECT MIN("Date")::VARCHAR AS min_date, MAX("Date")::VARCHAR AS max_date 
   FROM read_parquet('data/datasets/{id}.parquet')
   ```
4. **Staleness Heuristic**: Flags series staleness when the most recent historical observation is older than 60 days relative to today.
5. **Observation Threshold**: Requires $\ge 10$ historical periods for the selected frequency.

### Stage 2: Parquet Aggregation & Continuous Reindexing (`data_preparation.py`)
1. **Column-Pruned SQL Aggregation**: Queries Parquet directly via DuckDB with zero full-dataset memory loading:
   ```sql
   SELECT 
       date_trunc('month', "Date"::TIMESTAMP) AS period,
       SUM("Sales_Amount") AS metric_value
   FROM read_parquet('data/datasets/{id}.parquet')
   WHERE "Date" IS NOT NULL
   GROUP BY 1
   ORDER BY 1 ASC
   ```
   Supported aggregation functions: `SUM`, `AVG`, `COUNT`, `DISTINCT_COUNT`.
2. **Continuous Calendar Reindexing**:
   Real-world business data frequently skips weekends, holidays, or low-activity periods. The aggregated series is reindexed onto a continuous `pd.date_range` with regular frequency aliases (`D`, `W`, `M`, `Q`, `Y`).
3. **Policy-Driven Imputation**:
   - Volume metrics (`SUM`, `COUNT`, `DISTINCT_COUNT`): Filled with `0.0` (zero occurrences in missing periods).
   - Rate & Average metrics (`AVG`): Imputed with forward-fill (`ffill`), followed by backward-fill (`bfill`) to preserve continuity.

### Stage 3: Candidate Forecasting Algorithms (`trainer.py`)
Prediqo evaluates 5 candidate forecasting strategies per run:
1. **Naive Baseline Forecaster**:
   - Carries the most recent historical observation forward across all future horizon steps:
     $$\hat{y}_{T+h} = y_T$$
   - Serves as the benchmark to verify if more complex models add real predictive value.
2. **Seasonal Naive Forecaster**:
   - Replicates observations from the prior seasonal cycle of period $m$:
     $$\hat{y}_{T+h} = y_{T + h - m \cdot \lceil h/m \rceil}$$
   - Automatic seasonal cycle detection:
     - Daily (`D`): $m = 7$ (day-of-week seasonality)
     - Monthly (`M`): $m = 12$ (annual monthly seasonality)
     - Quarterly (`Q`): $m = 4$ (annual quarterly seasonality)
     - Fallback: $m = 1$ (reverts to Naive)
3. **Moving Average Forecaster**:
   - Computes rolling average over the last $w$ periods (evaluates $w=3$ or $w=7$ depending on series length):
     $$\hat{y}_{T+h} = \frac{1}{w} \sum_{i=0}^{w-1} y_{T-i}$$
4. **Linear Trend Forecaster**:
   - Fits an ordinary least-squares (OLS) slope and intercept over chronological step indices $t = 0, 1, \dots, T-1$:
     $$\hat{y}_{T+h} = \alpha + \beta (T + h)$$
5. **Exponential Smoothing Forecaster**:
   - Fits Holt's linear trend or Simple Exponential Smoothing with smoothing parameters $\alpha$ (level) and $\beta$ (trend):
     $$\ell_t = \alpha y_t + (1 - \alpha)(\ell_{t-1} + b_{t-1})$$
     $$b_t = \beta (\ell_t - \ell_{t-1}) + (1 - \beta) b_{t-1}$$
     $$\hat{y}_{T+h} = \ell_T + h \cdot b_T$$

### Stage 4: Chronological Backtesting & Evaluation (`evaluator.py`)
1. **Split Strategy**:
   - Splits series into training ($N - H$) and validation holdout ($H$), where $H = \text{forecast\_horizon}$ (bounded to $\le 30\%$ of total series length).
   - No random shuffling, ensuring temporal validity.
2. **Evaluation Metrics**:
   - **MAE** (Mean Absolute Error):
     $$\text{MAE} = \frac{1}{H} \sum_{t=1}^H |y_t - \hat{y}_t|$$
   - **RMSE** (Root Mean Squared Error):
     $$\text{RMSE} = \sqrt{\frac{1}{H} \sum_{t=1}^H (y_t - \hat{y}_t)^2}$$
   - **WAPE** (Weighted Absolute Percentage Error):
     $$\text{WAPE} = \frac{\sum |y_t - \hat{y}_t|}{\sum |y_t|}$$
   - **Zero-Safe MAPE**: If actual series contains $0.0$, MAPE is mathematically undefined. Prediqo returns `mape: null` with `mape_note: "Undefined due to actual values == 0"` rather than distorted infinity values.
3. **Benchmark Comparison (`vs_naive_pct`)**:
   - Quantifies percentage error difference compared to the Naive baseline:
     $$\text{vs\_naive\_pct} = \left(\frac{\text{MAE}_{\text{candidate}} - \text{MAE}_{\text{naive}}}{\text{MAE}_{\text{naive}}}\right) \times 100$$
   - Negative values indicate outperformance relative to baseline (e.g. $-18.5\%$ means $18.5\%$ lower error than Naive).
4. **Best Model Selection**:
   - The candidate with the **lowest backtest MAE** is automatically selected as `is_best: true`.

### Stage 5: Future Projection & Uncertainty Intervals (`forecaster.py`)
1. **Out-of-Sample Projections**:
   - Fits the winning forecaster on the **complete historical series** ($N$ points).
   - Projects timestamps strictly starting after the historical boundary $T_{\max}$.
2. **Uncertainty Intervals**:
   - Computes standard residual deviation $\sigma_e$ from historical backtest residuals.
   - Variance compounds with horizon step $h$ via $\sqrt{h}$:
     $$\text{Margin}_h = z \cdot \sigma_e \cdot \sqrt{h}$$
   - **80% Prediction Interval**: $z = 1.282$
   - **95% Prediction Interval**: $z = 1.960$
   - Ensures non-negative lower bounds when forecasting physical volume metrics.

---

## 3. Model Storage & Artifact Persistence (`model_store.py`)

Forecasting models are persisted in `data/models/fc_{model_id}/`:
- `metadata.json`: Dataset ID, version, target metric, date column, frequency, horizon, best algorithm, creation timestamp, and candidate model leaderboard.
- `historical_series.json`: Historical points `[{ date, value }]` for instant charting.
- `forecast_points.json`: Projected future points `[{ date, predicted, lower_80, upper_80, lower_95, upper_95 }]`.

---

## 4. API Reference

### 1. Forecast Feasibility
`GET /api/forecast/feasibility/{dataset_id}`

**Response**:
```json
{
  "dataset_id": "ds_a1b2c3d4",
  "dataset_version": 1,
  "date_columns": ["Order_Date", "Ship_Date"],
  "recommended_date_column": "Order_Date",
  "metric_columns": ["Sales_Amount", "Quantity", "Profit"],
  "recommended_metric_column": "Sales_Amount",
  "min_date": "2024-01-01",
  "max_date": "2024-12-31",
  "total_records": 10540,
  "is_stale": false,
  "staleness_message": null,
  "supported_frequencies": ["D", "W", "M", "Q", "Y"],
  "warnings": []
}
```

### 2. Train and Project Forecaster
`POST /api/forecast/train`

**Payload**:
```json
{
  "dataset_id": "ds_a1b2c3d4",
  "date_column": "Order_Date",
  "metric_column": "Sales_Amount",
  "frequency": "M",
  "forecast_horizon": 6,
  "aggregation_method": "SUM"
}
```

**Response**:
```json
{
  "model_id": "fc_7b82e1c0",
  "dataset_id": "ds_a1b2c3d4",
  "dataset_version": 1,
  "date_column": "Order_Date",
  "metric_column": "Sales_Amount",
  "frequency": "M",
  "forecast_horizon": 6,
  "best_model": {
    "algorithm": "ExponentialSmoothingForecaster",
    "primary_metric": "mae",
    "primary_metric_value": 1420.5,
    "metrics": {
      "mae": 1420.5,
      "rmse": 1845.2,
      "wape": 0.082,
      "mape": 8.4
    },
    "vs_naive_pct": -21.4,
    "selection_reason": "Lowest backtest MAE (1420.50 vs Naive 1807.10, -21.4% error reduction)"
  },
  "candidate_models": [
    {
      "algorithm": "NaiveForecaster",
      "metrics": { "mae": 1807.1, "rmse": 2210.0, "wape": 0.104, "mape": 10.8 },
      "vs_naive_pct": 0.0,
      "is_best": false
    },
    {
      "algorithm": "ExponentialSmoothingForecaster",
      "metrics": { "mae": 1420.5, "rmse": 1845.2, "wape": 0.082, "mape": 8.4 },
      "vs_naive_pct": -21.4,
      "is_best": true
    }
  ],
  "historical_series": [
    { "date": "2024-01-01", "value": 14200.0 }
  ],
  "forecast_points": [
    {
      "date": "2025-01-01",
      "predicted": 16400.0,
      "lower_80": 15200.0,
      "upper_80": 17600.0,
      "lower_95": 14500.0,
      "upper_95": 18300.0
    }
  ],
  "warnings": []
}
```

### 3. List Saved Forecast Models
`GET /api/forecast/models/{dataset_id}`

### 4. Get Forecast Model Details
`GET /api/forecast/models/{model_id}/details`

### 5. Out-of-Sample Reprojection
`POST /api/forecast/predict`

**Payload**:
```json
{
  "model_id": "fc_7b82e1c0",
  "horizon": 12
}
```

---

## 5. React Frontend User Interface

The frontend forecasting workflow is located in [`ForecastingTab.tsx`](file:///D:/AIML/prediqo-v2/frontend/src/components/ForecastingTab.tsx):
1. **Configuration Bar**: Interactive selectors for Date Column, Target Metric, Aggregation (`SUM`, `AVG`, `COUNT`), Frequency (`Daily`, `Weekly`, `Monthly`, `Quarterly`), and Forecast Horizon slider ($1 \dots 36$ steps).
2. **Interactive Charting (Recharts)**:
   - Historic observations rendered as a solid blue line.
   - Projected forecast values rendered as a distinct purple dashed line.
   - Shaded 95% uncertainty interval area band visually communicating future uncertainty.
   - Synchronized hover tooltip showing date, historic actuals, projected forecast, and 95% confidence bounds.
3. **Model Leaderboard**:
   - Table of candidate models highlighting the selected winner.
   - Metric columns: Backtest MAE, RMSE, WAPE, zero-safe MAPE, and relative improvement vs. Naive baseline (`vs_naive_pct`).
4. **Projection Schedule Table**: Tabular breakdown of future timestamps, point forecasts, and 80%/95% lower/upper bounds.
5. **Saved Forecasters Sidebar**: Quick access to previously trained models for instant reloads.

---

---

## 6. Phase 3 Forecasting Validation & Reliability

1. **Rolling-Origin Multi-Window Backtesting**:
   - For series with sufficient observations ($N \ge 2H + 4$), backtesting evaluates candidates over multiple sliding cutoff windows (up to 3 origins) rather than a single fixed split.
   - Prevents candidate model ranking from being dominated by anomalous single-window holdout events.
2. **Configurable Missing-Period Imputation**:
   - `zero`: Replaces non-active missing intervals with 0.0 (natural default for transaction volumes, order counts, sums).
   - `ffill`: Carries forward the last known observation (natural default for rates, prices, indices).
   - `bfill`: Backfills from subsequent observations.
   - `interpolate`: Computes linear trajectory between surrounding timestamps.
3. **Empirical Prediction Interval Coverage**:
   - Measures actual percentage of holdout points falling within nominal 80% and 95% uncertainty bands.
   - Attaches `interval_notes` when empirical coverage diverges from nominal levels or sample sizes are modest.
4. **Physical Boundary & Negative Detection**:
   - Automatic scan of historical observations for negative numbers (`has_negatives`).
   - If negative values exist in history (e.g. net profit, temperature, returns), models do not clip forecasts to zero unless explicitly requested (`non_negative=True`).
5. **Freshness & Staleness Diagnostics**:
   - Detects whether dataset timestamps end $> 60$ days ago and warns users that projections extend from a historical cutoff.

---

## 7. Roadmap for Further Development

1. **Multi-Series Grouped Forecasting**:
   - Support grouping dimensions (e.g. `GROUP BY Store_ID, date_trunc(...)`).
   - Fit hierarchical or top-down/bottom-up reconciled forecasts across departments or regions.
2. **Exogenous Regressors**:
   - Incorporate known future events (holiday calendar flags, planned marketing promotions, pricing changes).
3. **Advanced ML & Deep Forecasting Models**:
   - Recursive lag-feature gradient boosting (`LightGBM` / `XGBoost` with rolling statistics).
   - Integration with statistical toolkits (`statsmodels` SARIMAX, NeuralProphet).
4. **Automated Monitoring & Recalibration**:
   - Automated drift detection comparing new real-world arrivals against past forecast intervals.
