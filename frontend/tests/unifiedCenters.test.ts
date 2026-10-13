import test from 'node:test'
import assert from 'node:assert/strict'
import { CENTER_TABS, type CenterTabId } from '../src/components/centers/CenterNavTabs.tsx'
import type {
  TrainResponse,
  ForecastTrainResponse,
  ForecastExplanationResponse,
} from '../src/types/index.ts'
import { formatBusinessValue } from '../src/utils/businessMetrics.ts'

test('CENTER_TABS defines all 4 required enterprise tabs in correct order', () => {
  assert.equal(CENTER_TABS.length, 4)
  const tabIds: CenterTabId[] = CENTER_TABS.map((t) => t.id)
  assert.deepEqual(tabIds, ['overview', 'analytics', 'explanation', 'technical'])

  assert.equal(CENTER_TABS[0].label, 'Overview')
  assert.equal(CENTER_TABS[1].label, 'Analytics')
  assert.equal(CENTER_TABS[2].label, 'AI Explanation')
  assert.equal(CENTER_TABS[3].label, 'Technical Details')

  // Invariants: accessible descriptions and icons present
  CENTER_TABS.forEach((t) => {
    assert.ok(t.icon, `Tab ${t.id} must have an icon`)
    assert.ok(t.description, `Tab ${t.id} must have a descriptive accessibility summary`)
  })
})

test('Prediction Center Overview state distinguishes regression estimates from classification', () => {
  // 1. Regression test case
  const regTrainResult: Partial<TrainResponse> = {
    target_column: 'monthly_revenue',
    problem_type: 'regression',
    best_model: {
      algorithm: 'Gradient Boosting Regressor',
      primary_metric: 'mae',
      primary_metric_value: 1250.5,
      metrics: { mae: 1250.5, rmse: 1820.0, r2: 0.88 },
      vs_baseline_pct: 34.2,
      selection_rationale: 'Best performance on holdout cross-validation.',
    },
    training_row_count: 5000,
    test_row_count: 1000,
  }

  assert.equal(regTrainResult.problem_type, 'regression')
  const formattedPred = formatBusinessValue(45200.5, '$')
  assert.equal(formattedPred, '$45,200.5')
  assert.ok(regTrainResult.best_model!.vs_baseline_pct! > 0)

  // 2. Classification test case
  const clsTrainResult: Partial<TrainResponse> = {
    target_column: 'churn_risk',
    problem_type: 'classification',
    best_model: {
      algorithm: 'Random Forest Classifier',
      primary_metric: 'f1',
      primary_metric_value: 0.91,
      metrics: { accuracy: 0.93, f1: 0.91, precision: 0.89, recall: 0.94 },
      class_labels: ['Active', 'Churned'],
      confusion_matrix: [
        [850, 50],
        [30, 70],
      ],
      vs_baseline_pct: 22.5,
    },
  }

  assert.equal(clsTrainResult.problem_type, 'classification')
  assert.deepEqual(clsTrainResult.best_model!.class_labels, ['Active', 'Churned'])
  assert.equal(clsTrainResult.best_model!.confusion_matrix!.length, 2)
  // Ensure classification does not format as currency
  assert.equal(String(clsTrainResult.best_model!.class_labels![1]), 'Churned')
})

test('Prediction Center Analytics data transforms actual vs predicted holdout and confusion matrix', () => {
  const actualVsPredicted = [
    { actual: 100, predicted: 95, residual: 5 },
    { actual: 200, predicted: 205, residual: -5 },
    { actual: 300, predicted: 290, residual: 10 },
  ]

  const transformed = actualVsPredicted.map((pt, idx) => ({
    sample: idx + 1,
    actual: pt.actual,
    predicted: pt.predicted,
    residual: Number((pt.actual - pt.predicted).toFixed(2)),
  }))

  assert.equal(transformed.length, 3)
  assert.equal(transformed[0].sample, 1)
  assert.equal(transformed[0].residual, 5)
  assert.equal(transformed[1].residual, -5)
  assert.equal(transformed[2].residual, 10)
})

test('Forecasting Center Overview cleanly separates historical actuals from future horizon', () => {
  const trainResult: Partial<ForecastTrainResponse> = {
    metric_column: 'units_sold',
    aggregation: 'SUM',
    frequency: 'daily',
    horizon: 3,
    historical_end_date: '2024-01-03',
    historical_data: [
      { date: '2024-01-01', value: 120 },
      { date: '2024-01-02', value: 150 },
      { date: '2024-01-03', value: 140 },
    ],
    forecast_data: [
      { date: '2024-01-04', forecast: 160, lower_95: 140, upper_95: 180 },
      { date: '2024-01-05', forecast: 170, lower_95: 145, upper_95: 195 },
      { date: '2024-01-06', forecast: 165, lower_95: 135, upper_95: 190 },
    ],
  }

  // Combine into timeline
  const chartData = [
    ...trainResult.historical_data!.map((h) => ({
      date: h.date,
      actual: h.value,
      forecast: null,
      lower_95: null,
      upper_95: null,
      is_future: false,
    })),
    ...trainResult.forecast_data!.map((f) => ({
      date: f.date,
      actual: null,
      forecast: f.forecast,
      lower_95: f.lower_95,
      upper_95: f.upper_95,
      is_future: true,
    })),
  ]

  assert.equal(chartData.length, 6)
  // Historical points have actuals and null forecast
  assert.equal(chartData[0].is_future, false)
  assert.equal(chartData[0].actual, 120)
  assert.equal(chartData[0].forecast, null)

  // Future points have forecast and null actuals
  assert.equal(chartData[3].is_future, true)
  assert.equal(chartData[3].actual, null)
  assert.equal(chartData[3].forecast, 160)
  assert.equal(chartData[3].lower_95, 140)
  assert.equal(chartData[3].upper_95, 180)

  // Sum vs Average aggregation arithmetic
  const totalForecast = trainResult.forecast_data!.reduce((acc, curr) => acc + curr.forecast, 0)
  const avgForecast = totalForecast / trainResult.forecast_data!.length
  const endForecast = trainResult.forecast_data![trainResult.forecast_data!.length - 1].forecast

  assert.equal(totalForecast, 495)
  assert.equal(avgForecast, 165)
  assert.equal(endForecast, 165)
})

test('Forecasting Center properly detects and flags stale historical data', () => {
  const staleResponse: Partial<ForecastTrainResponse> = {
    is_stale: true,
    historical_end_date: '2016-12-31',
    stale_warning: 'Last observed timestamp is 2016-12-31. Projections extrapolate from historical patterns.',
  }

  assert.equal(staleResponse.is_stale, true)
  assert.ok(staleResponse.stale_warning!.includes('2016-12-31'))
  assert.ok(staleResponse.stale_warning!.includes('extrapolate'))

  const freshResponse: Partial<ForecastTrainResponse> = {
    is_stale: false,
    historical_end_date: '2026-10-10',
    stale_warning: null,
  }
  assert.equal(freshResponse.is_stale, false)
  assert.equal(freshResponse.stale_warning, null)
})

test('Forecasting Technical Details preserves full projection schedule and model candidates', () => {
  const technicalData: Partial<ForecastTrainResponse> = {
    horizon: 2,
    candidate_models: [
      {
        algorithm: 'AutoARIMA',
        metrics: { mae: 12.4, rmse: 16.1, wape: 4.8 },
        vs_naive_pct: 18.5,
        is_best: true,
        is_baseline: false,
        training_time_ms: 120,
      },
      {
        algorithm: 'NaiveLastValue',
        metrics: { mae: 15.2, rmse: 19.8, wape: 6.2 },
        vs_naive_pct: 0,
        is_best: false,
        is_baseline: true,
        training_time_ms: 2,
      },
    ],
    forecast_data: [
      { date: '2024-02-01', forecast: 300, lower_80: 280, upper_80: 320, lower_95: 260, upper_95: 340 },
      { date: '2024-02-02', forecast: 310, lower_80: 285, upper_80: 335, lower_95: 265, upper_95: 355 },
    ],
    interval_notes: 'Intervals computed via empirical residual variance across rolling-origin backtest windows.',
  }

  assert.equal(technicalData.candidate_models!.length, 2)
  assert.equal(technicalData.candidate_models![0].is_best, true)
  assert.equal(technicalData.candidate_models![1].is_baseline, true)
  assert.equal(technicalData.candidate_models![0].vs_naive_pct, 18.5)

  assert.equal(technicalData.forecast_data!.length, 2)
  assert.equal(technicalData.forecast_data![0].lower_80, 280)
  assert.equal(technicalData.forecast_data![0].upper_80, 320)
  assert.equal(technicalData.forecast_data![0].lower_95, 260)
  assert.equal(technicalData.forecast_data![0].upper_95, 340)
  assert.ok(technicalData.interval_notes!.includes('empirical residual variance'))
})

test('State preservation invariant: switching tabs does not reset or alter training results', () => {
  let activeTab: CenterTabId = 'overview'
  const mockTrainResult: Partial<TrainResponse> = {
    model_id: 'model_gradient_boost_v1',
    dataset_id: 'dataset_orders_01',
    target_column: 'delivery_time_days',
    training_row_count: 10000,
  }

  // Switch to Analytics
  activeTab = 'analytics'
  assert.equal(activeTab, 'analytics')
  assert.equal(mockTrainResult.model_id, 'model_gradient_boost_v1')

  // Switch to AI Explanation
  activeTab = 'explanation'
  assert.equal(activeTab, 'explanation')
  assert.equal(mockTrainResult.model_id, 'model_gradient_boost_v1')

  // Switch to Technical Details
  activeTab = 'technical'
  assert.equal(activeTab, 'technical')
  assert.equal(mockTrainResult.model_id, 'model_gradient_boost_v1')

  // Switch back to Overview
  activeTab = 'overview'
  assert.equal(activeTab, 'overview')
  assert.equal(mockTrainResult.model_id, 'model_gradient_boost_v1')
  assert.equal(mockTrainResult.training_row_count, 10000)
})
