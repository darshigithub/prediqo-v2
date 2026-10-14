# Prediqo Explainable AI (XAI) Architecture & Reference
## Phase 4A: Generic, Local-First Model Interpretability & Forecast Attribution

---

## 1. Overview & Principles

Prediqo's Explainable AI (XAI) layer delivers transparent, mathematically grounded, and trustworthy explanations for supervised machine learning predictions and time-series forecasts.

### Core Architecture Principles

1. **Local-First & Offline Resilience**: Operates entirely within the local environment without external cloud APIs, LLM calls, or unverified binary dependencies.
2. **Mathematical Exactness**:
   - For **Linear & Logistic Models**: Exact additive decomposition in the natural margin space ($w_j (x_j - \bar{x}_j)$).
   - For **Decision Trees & Ensembles (RandomForest, GradientBoosting)**: Exact decision-path telescoping sum attribution ($\Delta_k = V_{child} - V_{parent}$) with reconstruction error $< 10^{-14}$.
   - For **Dummy Baselines**: Constant baseline attribution with zero feature variance.
3. **Dataset-Agnostic & Schema-Flexible**: Works on any tabular dataset (retail, healthcare, SaaS, finance, operations) without hardcoded domain column names.
4. **Grouped Categorical Attribution**: Automatically groups one-hot encoded indicator columns back to their original parent categorical features by summing record-level contributions before aggregating.
5. **Zero Causal Claims for Forecasting**: Explicitly discloses that time-series trends, level states, and seasonal cycles represent historical patterns and extrapolation assumptions, never proving external causal mechanisms.
6. **Calibration Safety**: Discloses whether confidence scores are calibrated against holdout test distributions or uncalibrated heuristic model scores.

---

## 2. Explainability Architecture

The module resides in `backend/app/explainability/`:

```
backend/app/explainability/
├── __init__.py               # Module initialization
├── models.py                 # Pydantic schemas for requests, responses, and attribution items
├── feature_metadata.py       # Pipeline inspection, OneHotEncoder mapping, grouped contributions
├── local_explainer.py        # Exact additive decomposition (Linear, Tree ensembles, Baselines)
├── global_explainer.py       # Sample-based mean absolute contributions & collinearity detection
├── forecasting_explainer.py  # Trend slope, level state, seasonal cycles, empirical backtest coverage
└── service.py                # ExplainabilityService orchestrating model loading & version checks
```

---

## 3. Mathematical Foundations

### 3.1 Local Additive Decomposition

For any prediction input $x$, the local explanation decomposes the output into a baseline reference $Y_0$ and individual feature contributions $\Delta_j$:

$$\hat{y}(x) = Y_0 + \sum_{j=1}^{p} \Delta_j(x)$$

Where:
- **Baseline Reference ($Y_0$)**: Expected model output across the training/background sample $\mathbb{E}[f(X)]$.
- **Feature Contribution ($\Delta_j$)**: The signed change attributed to feature $j$ shifting from its reference to the record's value.
- **Direction**:
  - `POSITIVE`: Feature increases the predicted value or class log-odds margin.
  - `NEGATIVE`: Feature decreases the predicted value or class log-odds margin.
  - `NEUTRAL`: Zero contribution.
- **Relative Weight %**:
  
  $$\text{Relative Weight}_j = \frac{|\Delta_j|}{\sum_{k=1}^p |\Delta_k|} \times 100\%$$

### 3.2 Decision Tree & Random Forest Exact Attribution

For each decision tree in an ensemble, a record follows a unique root-to-leaf decision path $P = (v_0, v_1, \dots, v_L)$. The leaf prediction is:

$$f_{tree}(x) = v_L = v_0 + \sum_{k=1}^{L} (v_k - v_{k-1})$$

Each transition $v_{k-1} \to v_k$ is driven by the split feature $j = \text{feature}(v_{k-1})$. The exact tree-level attribution to feature $j$ is:

$$\Delta_j^{tree}(x) = \sum_{k \in P : \text{feature}(v_{k-1}) = j} (v_k - v_{k-1})$$

Averaging across all trees in a random forest or summing with learning rates in gradient boosting yields an exact telescoping sum with numerical reconstruction error bounded by floating-point precision ($< 10^{-14}$).

### 3.3 Grouped One-Hot Categorical Aggregation

When an original categorical column (e.g., `City`) is one-hot encoded into $K$ binary columns (`City_Austin`, `City_Dallas`, `City_Houston`), raw model features represent binary indicators.

Prediqo aggregates these at the individual record level **before** computing global metrics:

$$\Delta_{\text{City}}(x) = \sum_{k=1}^{K} \Delta_{\text{City}_k}(x)$$

For global importance, the mean absolute contribution is computed over $N$ sample rows:

$$\text{Global Importance}_C = \frac{1}{N} \sum_{i=1}^{N} \left| \Delta_C(x^{(i)}) \right|$$

---

## 4. REST API Endpoints

### 4.1 Explainability Feasibility
`GET /api/explainability/feasibility/{model_id}?model_type=prediction|forecasting`

Returns capability assessment, explanation methods supported, and exact decomposition confirmation.

### 4.2 Local Prediction Explanation
`POST /api/explainability/local`

**Request Body:**
```json
{
  "model_id": "mdl_a8b9c0d1",
  "features": {
    "Square_Feet": 2100,
    "Bedrooms": 3,
    "Neighborhood": "Suburban"
  },
  "target_class": null,
  "method_preference": "auto"
}
```

**Response:**
```json
{
  "model_id": "mdl_a8b9c0d1",
  "dataset_id": "ds_12345678",
  "dataset_version": 1,
  "problem_type": "regression",
  "algorithm": "Random Forest Regressor",
  "predicted_value": 345000.0,
  "baseline_reference_value": 310000.0,
  "reference_definition": "Sample average prediction baseline across background distribution",
  "decomposition_space": "prediction_output",
  "contributions": [
    {
      "feature": "Square_Feet",
      "raw_value": 2100,
      "contribution": 25000.0,
      "direction": "POSITIVE",
      "relative_weight_pct": 71.4,
      "transformed_components": null
    },
    {
      "feature": "Neighborhood",
      "raw_value": "Suburban",
      "contribution": 10000.0,
      "direction": "POSITIVE",
      "relative_weight_pct": 28.6,
      "transformed_components": [
        {"name": "Neighborhood_Suburban", "value": 1.0, "contribution": 10000.0}
      ]
    }
  ],
  "additive_sum": 35000.0,
  "reconstruction_error": 0.0,
  "validation_status": "EXACT_ADDITIVE",
  "explanation_method": "exact_tree_path_decomposition",
  "is_calibrated": true,
  "confidence_metric_name": "calibrated_probability",
  "warnings": [],
  "limitations": [
    "Feature contributions reflect model decision logic and training associations, not necessarily real-world causal mechanisms."
  ],
  "generated_at": "2026-10-10T16:00:00Z"
}
```

### 4.3 Global Model Explanation
`GET /api/explainability/global/{model_id}?max_sample_rows=100`

Returns grouped feature importance across background sample rows, with collinearity warnings for features with $|\rho| \ge 0.85$.

### 4.4 Forecast Explanation & Trend Drivers
`GET /api/explainability/forecast/{model_id}`

Returns trend slope, intercept, level state, seasonal repeating cycle, backtest MAE/RMSE, empirical coverage, and non-causal disclosures.

---

## 5. Frontend User Experience

### 5.1 Prediction Center (`PredictionPage.tsx`)
- **Live Prediction Drivers (AI Explanation Tab)**: When a prediction is generated, automatically displays signed feature contributions with color-coded direction badges (`+` Green, `−` Red), magnitude bars, and relative weight %.
- **Exact Additive Reconstruction (Technical Details Tab)**: Confirms $Y_0 + \sum \Delta_j = \hat{y}$ with an exact additive status badge and machine-precision reconstruction log ($< 10^{-14}$).
- **Encoded Components Accordion**: Expandable view for categorical features with multiple one-hot columns.
- **Global XAI Toggle**: Switches the feature importance view to grouped original features with correlation warnings.

### 5.2 Forecasting Center (`ForecastingPage.tsx`)
- **Trend Drivers & Rationale (AI Explanation Tab)**: Explains linear slope, recent momentum change %, and projection rationale (e.g., linear drift vs. recursive exponential smoothing).
- **Interval Reliability (Analytics Tab)**: Visualizes empirical interval coverage (nominal 80% and 95%) achieved on historical holdout windows.
- **Non-Causal Disclosures**: Clear guidance on extrapolation assumptions and statistical limitations across all tabs.

---

## 6. Diagnostic and Mathematical Repairs (Audit Log)

During the diagnostic audit and repair of the XAI layer, the following defects were identified, mathematically resolved, and validated with regression tests:

### 6.1 Multiclass & Binary GBDT Initial Prediction
- **Problem**: In `backend/app/explainability/local_explainer.py`, calling `estimator.init_.predict(x2d)` for multiclass GBDT returned a 1D array of class strings `array(['Low'])`, resulting in `IndexError: too many indices for array` when indexing `[0, cls_idx]`. For binary classification with imbalanced targets, `init_.predict` returned `0.0` instead of the true log-odds prior $\ln(p/(1-p))$, causing reconstruction error $\sim 1.32$ instead of machine zero.
- **Resolution**: Replaced `init_.predict` with `estimator._raw_predict_init(x2d)` (shape `(1, 1)` in binary, shape `(1, n_classes)` in multiclass).
- **Result**: Reduced GBDT reconstruction error to machine precision ($< 10^{-14}$, exact additive status verified across all classes and target imbalances).

### 6.2 Frontend-Backend Contract Synchronization
- **Problem**: Backend emitted fields (`reference_value`, `output_scale`, `feature_contributions`, `sample_size`, `features`, `correlated_features_warning`), whereas `frontend/src/types/index.ts` and `PredictionTab.tsx` expected (`baseline_reference_value`, `decomposition_space`, `contributions`, `sample_rows_evaluated`, `feature_importances`, `correlation_warnings`, `item.raw_value`, `tc.name`).
- **Resolution**: Updated `LocalExplanationResponse`, `GlobalExplanationResponse`, `FeatureContributionItem`, and `GroupedFeatureImportanceItem` to support both sets of field names concurrently.

### 6.3 Separation of Classification Spaces
- **Problem**: Risk of confusing probability shifts with log-odds margins.
- **Resolution**:
  - `RandomForestClassifier`: Decomposed in `PROBABILITY_SPACE` ($P_{\text{target}} = \text{ref} + \sum \Delta$), where each tree's path leaf voting frequency telescopes cleanly to ensemble probability.
  - `LogisticRegression` and `GradientBoostingClassifier`: Decomposed in `LOG_ODDS_MARGIN` space ($z_{\text{margin}} = \text{ref} + \sum \Delta$). The UI clearly labels the decomposition space as `LOG_ODDS_MARGIN` and explains that sigmoid/softmax transformations are non-linear.

### 6.4 API Route Harmonization
- **Problem**: Frontend called `/explainability/local`, `/explainability/global/{model_id}`, and `/explainability/forecast/{model_id}`, while backend mounted `/explainability/models/{model_id}/local` and `/explainability/models/{model_id}/global`.
- **Resolution**: Mounted both direct endpoints and parameterized endpoints under `/api/explainability/`, ensuring full interoperability with frontend components and external API callers. Also updated `/api/explainability/feasibility/{identifier}` to resolve model IDs back to dataset IDs automatically.
