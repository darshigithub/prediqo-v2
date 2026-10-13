/**
 * Business-Friendly Metric Explanations and Formatting Utilities.
 * Translates technical ML and forecasting metrics into plain-language business insights
 * without modifying or inventing authoritative numbers.
 */

export interface MetricInsight {
  metricName: string
  displayName: string
  formattedValue: string
  technicalExplanation: string
  businessMeaning: string
  statusTier: 'excellent' | 'good' | 'moderate' | 'caution'
}

/**
 * Formats a numeric value with optional units and sensible decimal precision.
 */
export function formatBusinessValue(
  value: number | string | null | undefined,
  unit?: string | null,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return 'N/A'
  const num = typeof value === 'number' ? value : Number(value)
  if (isNaN(num)) return String(value)

  const isNeg = num < 0
  const absNum = Math.abs(num)
  const formattedNum = absNum.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })

  if (!unit) return isNeg ? `-${formattedNum}` : formattedNum
  if (unit === '$') return isNeg ? `-$${formattedNum}` : `$${formattedNum}`
  if (unit === '%') return isNeg ? `-${formattedNum}%` : `${formattedNum}%`
  return isNeg ? `-${formattedNum} ${unit}` : `${formattedNum} ${unit}`
}

/**
 * Returns plain-language business explanation for regression metrics.
 */
export function explainRegressionMetrics(
  metrics: Record<string, any>,
  targetName: string,
  unit?: string | null
): MetricInsight[] {
  const insights: MetricInsight[] = []

  // 1. R-Squared (R²)
  if (metrics.r2 !== undefined && metrics.r2 !== null) {
    const r2Val = Number(metrics.r2)
    const pctExplained = Math.round(Math.max(0, Math.min(100, r2Val * 100)))
    const unExplained = 100 - pctExplained

    let tier: MetricInsight['statusTier'] = 'moderate'
    let meaning = `The model explains ${pctExplained}% of historical variation in ${targetName}. About ${unExplained}% is driven by unmeasured external factors.`
    if (r2Val >= 0.8) {
      tier = 'excellent'
      meaning = `High Predictive Fit: The model captures ${pctExplained}% of historical fluctuations in ${targetName}.`
    } else if (r2Val >= 0.6) {
      tier = 'good'
      meaning = `Moderate Fit: The model accounts for ${pctExplained}% of changes in ${targetName}.`
    } else if (r2Val < 0.3) {
      tier = 'caution'
      meaning = `Low Explanatory Power: Only ${pctExplained}% of variation is captured. Predictions carry elevated uncertainty.`
    }

    insights.push({
      metricName: 'r2',
      displayName: 'Variance Explained (R²)',
      formattedValue: `${r2Val.toFixed(2)} (${pctExplained}%)`,
      technicalExplanation: 'Coefficient of determination (R-squared) on holdout test set.',
      businessMeaning: meaning,
      statusTier: tier,
    })
  }

  // 2. Mean Absolute Error (MAE)
  if (metrics.mae !== undefined && metrics.mae !== null) {
    const maeVal = Number(metrics.mae)
    insights.push({
      metricName: 'mae',
      displayName: 'Average Expected Error (MAE)',
      formattedValue: formatBusinessValue(maeVal, unit),
      technicalExplanation: 'Mean Absolute Error across holdout test records.',
      businessMeaning: `On average, predictions are within ±${formatBusinessValue(maeVal, unit)} of actual outcomes.`,
      statusTier: 'good',
    })
  }

  // 3. Root Mean Squared Error (RMSE)
  if (metrics.rmse !== undefined && metrics.rmse !== null) {
    const rmseVal = Number(metrics.rmse)
    insights.push({
      metricName: 'rmse',
      displayName: 'Large-Error Sensitivity (RMSE)',
      formattedValue: formatBusinessValue(rmseVal, unit),
      technicalExplanation: 'Root Mean Squared Error penalizing large residual deviations.',
      businessMeaning: `Standard deviation of residuals is ${formatBusinessValue(rmseVal, unit)}. Highlights vulnerability to occasional major misses.`,
      statusTier: 'good',
    })
  }

  // 4. Mean Absolute Percentage Error (MAPE)
  if (metrics.mape !== undefined && metrics.mape !== null) {
    const mapeVal = Number(metrics.mape)
    let tier: MetricInsight['statusTier'] = 'good'
    if (mapeVal <= 10) tier = 'excellent'
    else if (mapeVal <= 25) tier = 'good'
    else tier = 'caution'

    insights.push({
      metricName: 'mape',
      displayName: 'Relative Error (MAPE)',
      formattedValue: `${mapeVal.toFixed(1)}%`,
      technicalExplanation: 'Mean Absolute Percentage Error on non-zero holdout points.',
      businessMeaning: `Predictions deviate by an average of ${mapeVal.toFixed(1)}% relative to actual values.`,
      statusTier: tier,
    })
  }

  return insights
}

/**
 * Returns plain-language business explanation for classification metrics.
 */
export function explainClassificationMetrics(
  metrics: Record<string, any>,
  _targetName?: string,
  _classLabels?: string[] | null
): MetricInsight[] {
  const insights: MetricInsight[] = []

  // 1. Accuracy
  if (metrics.accuracy !== undefined && metrics.accuracy !== null) {
    const acc = Number(metrics.accuracy)
    const accPct = (acc * 100).toFixed(1)
    let tier: MetricInsight['statusTier'] = 'good'
    if (acc >= 0.9) tier = 'excellent'
    else if (acc < 0.7) tier = 'caution'

    insights.push({
      metricName: 'accuracy',
      displayName: 'Overall Accuracy',
      formattedValue: `${accPct}%`,
      technicalExplanation: 'Proportion of correct classifications across all holdout test records.',
      businessMeaning: `The model correctly identified the status in ${accPct} out of every 100 evaluation cases.`,
      statusTier: tier,
    })
  }

  // 2. F1 Score
  if (metrics.f1 !== undefined && metrics.f1 !== null) {
    const f1Val = Number(metrics.f1)
    let tier: MetricInsight['statusTier'] = 'good'
    if (f1Val >= 0.85) tier = 'excellent'
    else if (f1Val < 0.65) tier = 'caution'

    insights.push({
      metricName: 'f1',
      displayName: 'Balanced Quality (F1 Score)',
      formattedValue: f1Val.toFixed(2),
      technicalExplanation: 'Harmonic mean of precision and recall (0.0 to 1.0).',
      businessMeaning: `Balanced score of ${(f1Val * 100).toFixed(1)}/100, accounting for both false alarms and missed cases.`,
      statusTier: tier,
    })
  }

  // 3. Precision
  if (metrics.precision !== undefined && metrics.precision !== null) {
    const prec = Number(metrics.precision)
    insights.push({
      metricName: 'precision',
      displayName: 'Precision (False Alarm Rate)',
      formattedValue: `${(prec * 100).toFixed(1)}%`,
      technicalExplanation: 'True positives divided by all predicted positive labels.',
      businessMeaning: `When the model predicts a specific status, it is correct ${(prec * 100).toFixed(1)}% of the time.`,
      statusTier: prec >= 0.8 ? 'good' : 'moderate',
    })
  }

  // 4. Recall
  if (metrics.recall !== undefined && metrics.recall !== null) {
    const rec = Number(metrics.recall)
    insights.push({
      metricName: 'recall',
      displayName: 'Coverage (Recall Rate)',
      formattedValue: `${(rec * 100).toFixed(1)}%`,
      technicalExplanation: 'True positives divided by all actual positive occurrences.',
      businessMeaning: `The model successfully catches ${(rec * 100).toFixed(1)}% of all real occurrences, missing ${((1 - rec) * 100).toFixed(1)}%.`,
      statusTier: rec >= 0.8 ? 'good' : 'moderate',
    })
  }

  return insights
}

/**
 * Returns plain-language business explanation for time-series forecasting metrics.
 */
export function explainForecastingMetrics(
  metrics: Record<string, any>,
  _metricName: string,
  frequency: string,
  unit?: string | null
): MetricInsight[] {
  const insights: MetricInsight[] = []

  // 1. Validation MAE
  if (metrics.mae !== undefined && metrics.mae !== null) {
    const mae = Number(metrics.mae)
    insights.push({
      metricName: 'mae',
      displayName: 'Backtest Average Error (MAE)',
      formattedValue: formatBusinessValue(mae, unit),
      technicalExplanation: 'Mean Absolute Error measured over rolling chronological holdout windows.',
      businessMeaning: `During historical testing, projections differed by an average of ±${formatBusinessValue(mae, unit)} per ${frequency}.`,
      statusTier: 'good',
    })
  }

  // 2. WAPE
  if (metrics.wape !== undefined && metrics.wape !== null) {
    const wape = Number(metrics.wape)
    let tier: MetricInsight['statusTier'] = 'good'
    if (wape <= 15) tier = 'excellent'
    else if (wape <= 30) tier = 'good'
    else tier = 'caution'

    insights.push({
      metricName: 'wape',
      displayName: 'Weighted Percentage Error (WAPE)',
      formattedValue: `${wape.toFixed(1)}%`,
      technicalExplanation: 'Sum of absolute errors divided by sum of actual values.',
      businessMeaning: `Overall volume error is ${wape.toFixed(1)}% across the forecast horizon.`,
      statusTier: tier,
    })
  }

  // 3. RMSE
  if (metrics.rmse !== undefined && metrics.rmse !== null) {
    const rmse = Number(metrics.rmse)
    insights.push({
      metricName: 'rmse',
      displayName: 'Peak-Volatility Error (RMSE)',
      formattedValue: formatBusinessValue(rmse, unit),
      technicalExplanation: 'Root Mean Squared Error emphasizing peak spikes and demand surges.',
      businessMeaning: `Measures error during sudden swings or volatile periods (${formatBusinessValue(rmse, unit)}).`,
      statusTier: 'good',
    })
  }

  return insights
}

/**
 * Builds baseline comparison narrative.
 */
export function explainBaselineComparison(
  vsBaselinePct: number | null | undefined,
  _problemType?: string
): { headline: string; description: string; isPositive: boolean } {
  if (vsBaselinePct === null || vsBaselinePct === undefined) {
    return {
      headline: 'Benchmark Baseline Model',
      description: 'Reference model used as the baseline comparison.',
      isPositive: false,
    }
  }

  if (vsBaselinePct > 0) {
    return {
      headline: `${vsBaselinePct}% Improvement over Baseline`,
      description: `This trained model reduces forecast/prediction error by ${vsBaselinePct}% compared to a naive historical baseline model.`,
      isPositive: true,
    }
  }

  if (vsBaselinePct < 0) {
    return {
      headline: `${Math.abs(vsBaselinePct)}% Below Baseline`,
      description: `The candidate model performed worse than naive historical guessing. Review features and data quality.`,
      isPositive: false,
    }
  }

  return {
    headline: 'Matches Baseline Accuracy',
    description: 'The trained model matches the naive historical average without significant uplift.',
    isPositive: false,
  }
}
