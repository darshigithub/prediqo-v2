import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatBusinessValue,
  explainRegressionMetrics,
  explainClassificationMetrics,
  explainForecastingMetrics,
  explainBaselineComparison,
} from '../src/utils/businessMetrics.ts'

test('formatBusinessValue correctly handles numbers, nulls, and units', () => {
  assert.equal(formatBusinessValue(null), 'N/A')
  assert.equal(formatBusinessValue(undefined), 'N/A')
  assert.equal(formatBusinessValue(1250, '$'), '$1,250')
  assert.equal(formatBusinessValue(85.5, '%'), '85.5%')
  assert.equal(formatBusinessValue(14, 'days'), '14 days')
  assert.equal(formatBusinessValue(250, 'units'), '250 units')
  assert.equal(formatBusinessValue(1234567.89, '$', 2), '$1,234,567.89')
  assert.equal(formatBusinessValue(-1500, '$'), '-$1,500')
})

test('explainRegressionMetrics generates accurate business explanations', () => {
  const metrics = {
    r2: 0.85,
    mae: 120.5,
    rmse: 145.2,
    mape: 8.5,
  }

  const insights = explainRegressionMetrics(metrics, 'Monthly Revenue', '$')
  assert.equal(insights.length, 4)

  const r2Insight = insights.find((i) => i.metricName === 'r2')
  assert.ok(r2Insight)
  assert.equal(r2Insight.statusTier, 'excellent')
  assert.ok(r2Insight.businessMeaning.includes('85%'))
  assert.ok(r2Insight.businessMeaning.includes('Monthly Revenue'))

  const maeInsight = insights.find((i) => i.metricName === 'mae')
  assert.ok(maeInsight)
  assert.ok(maeInsight.businessMeaning.includes('±$120.5'))

  const mapeInsight = insights.find((i) => i.metricName === 'mape')
  assert.ok(mapeInsight)
  assert.equal(mapeInsight.statusTier, 'excellent')
  assert.ok(mapeInsight.formattedValue.includes('8.5%'))
})

test('explainClassificationMetrics generates accurate business explanations', () => {
  const metrics = {
    accuracy: 0.92,
    f1: 0.88,
    precision: 0.89,
    recall: 0.87,
  }

  const insights = explainClassificationMetrics(metrics, 'Churn Status', ['Active', 'Churned'])
  assert.equal(insights.length, 4)

  const accInsight = insights.find((i) => i.metricName === 'accuracy')
  assert.ok(accInsight)
  assert.equal(accInsight.formattedValue, '92.0%')
  assert.equal(accInsight.statusTier, 'excellent')
  assert.ok(accInsight.businessMeaning.includes('92.0 out of every 100'))

  const f1Insight = insights.find((i) => i.metricName === 'f1')
  assert.ok(f1Insight)
  assert.equal(f1Insight.formattedValue, '0.88')
  assert.ok(f1Insight.businessMeaning.includes('88.0/100'))
})

test('explainForecastingMetrics translates holdout error to business terms', () => {
  const metrics = {
    mae: 55.2,
    wape: 12.4,
    rmse: 70.1,
  }

  const insights = explainForecastingMetrics(metrics, 'Weekly Demand', 'week', 'units')
  assert.equal(insights.length, 3)

  const maeInsight = insights.find((i) => i.metricName === 'mae')
  assert.ok(maeInsight)
  assert.ok(maeInsight.businessMeaning.includes('±55.2 units per week'))

  const wapeInsight = insights.find((i) => i.metricName === 'wape')
  assert.ok(wapeInsight)
  assert.equal(wapeInsight.statusTier, 'excellent')
  assert.ok(wapeInsight.businessMeaning.includes('12.4% across the forecast horizon'))
})

test('explainBaselineComparison handles uplift, degradation, and baseline models', () => {
  const uplift = explainBaselineComparison(24.5, 'regression')
  assert.equal(uplift.isPositive, true)
  assert.ok(uplift.headline.includes('24.5% Improvement'))
  assert.ok(uplift.description.includes('reduces forecast/prediction error by 24.5%'))

  const degraded = explainBaselineComparison(-10.2, 'regression')
  assert.equal(degraded.isPositive, false)
  assert.ok(degraded.headline.includes('10.2% Below Baseline'))

  const baseline = explainBaselineComparison(null, 'regression')
  assert.equal(baseline.isPositive, false)
  assert.equal(baseline.headline, 'Benchmark Baseline Model')
})
