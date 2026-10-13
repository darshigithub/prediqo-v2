import test from 'node:test'
import assert from 'node:assert/strict'
import type {
  AIExplanationResponse,
  PredictionAIExplanationRequest,
  ForecastAIExplanationRequest,
} from '../src/types/index.ts'

test('AIExplanationResponse adheres to verified schema contract', () => {
  const sampleResponse: AIExplanationResponse = {
    summary: 'The model predicts monthly_sales will be 45,200.50 USD.',
    what_the_result_means: 'Point projection for operational capacity and budget allocation.',
    supporting_evidence: [
      "Feature 'marketing_spend' increased prediction by +5,200.50 USD.",
    ],
    evaluation_quality: 'Trained using Supervised ML. Holdout/CV MAE is 1200.0.',
    uncertainty_and_limitations: [
      'Non-Causal Relationship: Feature attributions represent statistical associations across training data.',
      'These results are estimates based on the available data. Actual outcomes may differ.',
    ],
    suggested_verifications: [
      'Verify that current input parameters reflect real operational conditions.',
    ],
    provider: 'ollama',
    model: 'llama3.2',
    generated_at: '2026-10-12T16:00:00Z',
    is_fallback: false,
    cache_hit: true,
    evidence_fingerprint: 'a1b2c3d4e5f6',
    raw_evidence: { target_name: 'monthly_sales', prediction: 45200.5 },
  }

  assert.equal(sampleResponse.provider, 'ollama')
  assert.equal(sampleResponse.cache_hit, true)
  assert.equal(sampleResponse.is_fallback, false)
  assert.ok(sampleResponse.supporting_evidence.length >= 1)
  assert.ok(sampleResponse.uncertainty_and_limitations.length >= 2)
  assert.ok(sampleResponse.suggested_verifications.length >= 1)
  assert.ok(sampleResponse.evidence_fingerprint.length > 0)
})

test('Deterministic fallback response maintains identical response contract', () => {
  const fallbackResponse: AIExplanationResponse = {
    summary: 'Over the next 14 daily periods, revenue is projected to follow a stable trajectory.',
    what_the_result_means: 'Expected cumulative requirement of 14,000.00 USD across the horizon.',
    supporting_evidence: ['Historical average was 1,000.00 USD.'],
    evaluation_quality: 'Holdout WAPE is 8.5%.',
    uncertainty_and_limitations: [
      'Non-Guarantee: Time-series forecasts extrapolate historical patterns.',
      'Forecast intervals indicate statistical uncertainty bounds rather than fixed future outcomes.',
    ],
    suggested_verifications: ['Monitor actuals weekly against trajectory.'],
    provider: 'deterministic_fallback',
    model: 'rules_engine_v1',
    generated_at: '2026-10-12T16:00:00Z',
    is_fallback: true,
    cache_hit: false,
    evidence_fingerprint: 'fedcba654321',
  }

  assert.equal(fallbackResponse.is_fallback, true)
  assert.equal(fallbackResponse.provider, 'deterministic_fallback')
  assert.ok(fallbackResponse.summary.length > 0)
  assert.ok(fallbackResponse.what_the_result_means.length > 0)
  assert.ok(fallbackResponse.uncertainty_and_limitations.some(l => l.includes('Non-Guarantee') || l.includes('uncertainty bounds')))
})

test('PredictionAIExplanationRequest properly normalizes feature contributions and units', () => {
  const req: PredictionAIExplanationRequest = {
    target_name: 'churn_risk',
    problem_type: 'classification',
    unit: null,
    prediction: 'High',
    probabilities: { High: 0.85, Low: 0.15 },
    contributions: [
      { feature: 'late_payments', contribution: 1.2, raw_value: 3 },
      { feature: 'account_age', contribution: -0.4, raw_value: 24 },
    ],
    metrics: { f1: 0.88 },
    provider: 'groq',
    model: 'llama-3.3-70b-versatile',
    force_fallback: false,
    bypass_cache: true,
  }

  assert.equal(req.target_name, 'churn_risk')
  assert.equal(req.problem_type, 'classification')
  assert.equal(req.probabilities?.['High'], 0.85)
  assert.equal(req.contributions?.length, 2)
  assert.equal(req.bypass_cache, true)
})

test('ForecastAIExplanationRequest properly formats horizon and interval aggregations', () => {
  const req: ForecastAIExplanationRequest = {
    metric_column: 'order_demand',
    frequency: 'weekly',
    horizon: 8,
    aggregation: 'SUM',
    unit: 'boxes',
    forecast_summary: {
      forecast_mean: 350.0,
      forecast_total: 2800.0,
      trajectory: 'upward',
    },
    backtest_metrics: {
      mae: 22.0,
      mape: 6.2,
      directional_accuracy: 0.81,
    },
    intervals: {
      lower_bound_mean: 310.0,
      upper_bound_mean: 395.0,
      nominal_coverage_pct: 95,
    },
    limitations: ['Supplier lead time anomalies during holiday weeks'],
  }

  assert.equal(req.metric_column, 'order_demand')
  assert.equal(req.frequency, 'weekly')
  assert.equal(req.horizon, 8)
  assert.equal(req.unit, 'boxes')
  assert.equal(req.forecast_summary?.forecast_total, 2800.0)
  assert.equal(req.backtest_metrics?.mape, 6.2)
  assert.equal(req.intervals?.nominal_coverage_pct, 95)
  assert.ok(req.limitations?.includes('Supplier lead time anomalies during holiday weeks'))
})
