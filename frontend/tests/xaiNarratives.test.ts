import test from 'node:test'
import assert from 'node:assert/strict'
import {
  generateLocalNarrative,
  generateGlobalNarrative,
  generateForecastNarrative,
} from '../src/utils/xaiNarratives.ts'
import type {
  LocalExplanationResponse,
  GlobalExplanationResponse,
  ForecastExplanationResponse,
} from '../src/types/index.ts'

test('generateLocalNarrative produces clear drivers and scale disclosures for regression', () => {
  const explanation: LocalExplanationResponse = {
    model_id: 'test-model-1',
    dataset_id: 'dataset-1',
    dataset_version: 1,
    problem_type: 'regression',
    algorithm: 'RandomForestRegressor',
    decomposition_space: 'ORIGINAL_OUTPUT_SPACE',
    baseline_reference_value: 50000,
    reference_definition: 'Empirical expected output E[Y] across 1,000 training records',
    raw_model_prediction: 62500,
    additive_sum: 12500,
    reconstruction_error: 0.00001,
    validation_status: 'EXACT_ADDITIVE',
    explanation_method: 'tree_path_decomposition',
    tolerance_applied: 0.001,
    is_calibrated: true,
    contributions: [
      {
        feature: 'SquareFootage',
        raw_value: 2400,
        contribution: 10000,
        direction: 'POSITIVE',
        relative_weight_pct: 66.7,
      },
      {
        feature: 'LocationScore',
        raw_value: 8.5,
        contribution: 4000,
        direction: 'POSITIVE',
        relative_weight_pct: 26.7,
      },
      {
        feature: 'PropertyAge',
        raw_value: 25,
        contribution: -1500,
        direction: 'NEGATIVE',
        relative_weight_pct: 10.0,
      },
    ],
    limitations: ['Tree-based explanations reflect training partition density.'],
  }

  const narrative = generateLocalNarrative(explanation, 'HousePrice', '$')
  assert.ok(narrative)
  assert.equal(narrative.topPositiveDrivers.length, 2)
  assert.equal(narrative.topNegativeDrivers.length, 1)

  assert.equal(narrative.topPositiveDrivers[0].feature, 'SquareFootage')
  assert.ok(narrative.topPositiveDrivers[0].impactText.includes('+$10,000'))

  assert.equal(narrative.topNegativeDrivers[0].feature, 'PropertyAge')
  assert.ok(narrative.topNegativeDrivers[0].impactText.includes('-$1,500'))

  assert.ok(narrative.summaryParagraph.includes('SquareFootage'))
  assert.ok(narrative.summaryParagraph.includes('PropertyAge'))
  assert.ok(narrative.scaleDisclosure.includes('original target units ($)'))
  assert.ok(narrative.attributionDisclaimer.includes('Statistical Attribution Notice'))
})

test('generateLocalNarrative correctly warns on LOG_ODDS_MARGIN space', () => {
  const explanation: LocalExplanationResponse = {
    model_id: 'test-model-2',
    dataset_id: 'dataset-1',
    dataset_version: 1,
    problem_type: 'classification',
    algorithm: 'LogisticRegression',
    decomposition_space: 'LOG_ODDS_MARGIN',
    baseline_reference_value: -0.45,
    reference_definition: 'Log-odds model intercept beta_0',
    raw_model_prediction: 1.25,
    additive_sum: 1.70,
    reconstruction_error: 0.00002,
    validation_status: 'EXACT_ADDITIVE',
    explanation_method: 'linear_additive',
    tolerance_applied: 0.001,
    is_calibrated: false,
    contributions: [
      {
        feature: 'AccountTenure',
        raw_value: 3,
        contribution: 1.2,
        direction: 'POSITIVE',
        relative_weight_pct: 70.6,
      },
    ],
    limitations: [],
  }

  const narrative = generateLocalNarrative(explanation, 'ChurnStatus')
  assert.ok(narrative)
  assert.ok(narrative.scaleDisclosure.includes('log-odds'))
  assert.ok(narrative.scaleDisclosure.includes('not direct percentage point changes in final probability'))
  assert.ok(narrative.topPositiveDrivers[0].impactText.includes('log-odds pts'))
})

test('generateGlobalNarrative summarizes top dataset-wide drivers', () => {
  const explanation: GlobalExplanationResponse = {
    model_id: 'test-model-3',
    dataset_id: 'dataset-1',
    dataset_version: 1,
    problem_type: 'regression',
    algorithm: 'GradientBoostingRegressor',
    explanation_method: 'permutation_global_attribution',
    sample_rows_evaluated: 250,
    total_dataset_rows: 1000,
    feature_importances: [
      {
        feature: 'MonthlySpend',
        mean_absolute_contribution: 450.2,
        relative_share_pct: 48.5,
      },
      {
        feature: 'ContractMonths',
        mean_absolute_contribution: 280.1,
        relative_share_pct: 30.2,
      },
    ],
    correlation_warnings: ['MonthlySpend is highly collinear with TotalSpend (r=0.89)'],
  }

  const narrative = generateGlobalNarrative(explanation, 'CustomerLTV')
  assert.ok(narrative)
  assert.ok(narrative.summaryParagraph.includes('MonthlySpend'))
  assert.ok(narrative.summaryParagraph.includes('ContractMonths'))
  assert.ok(narrative.collinearityNote?.includes('collinear with TotalSpend'))
})

test('generateForecastNarrative produces executive trend, momentum and reliability summary', () => {
  const explanation: ForecastExplanationResponse = {
    model_id: 'fc-1',
    dataset_id: 'dataset-1',
    dataset_version: 1,
    date_column: 'date',
    horizon: 14,
    explanation_method: 'time_series_component_attribution',
    metric_column: 'DailySales',
    algorithm: 'Holt-Winters Exponential Smoothing',
    frequency: 'daily',
    aggregation: 'SUM',
    historical_trend: 'Upward',
    trend_slope: 15.4,
    recent_change_pct: 8.2,
    recent_observation_reference: 1420.0,
    backtest_mae: 32.5,
    backtest_strategy: 'rolling_origin',
    evaluation_windows: 3,
    empirical_coverage_80: 82.5,
    empirical_coverage_95: 96.0,
    selection_reason: 'Selected as best candidate based on lowest backtest MAE.',
    limitations: ['Assumes continuity of observed seasonality.'],
  }

  const narrative = generateForecastNarrative(explanation, 'DailySales', 'day', '$')
  assert.ok(narrative)
  assert.ok(narrative.trendInsight.includes('upward'))
  assert.ok(narrative.trendInsight.includes('$15.4 per day'))
  assert.ok(narrative.momentumInsight.includes('+8.2%'))
  assert.ok(narrative.intervalReliability.includes('96% of holdout observations fell within the modeled 95% uncertainty band'))
  assert.ok(narrative.nonCausalDisclosure.includes('Time-Series Projection Notice'))
})
