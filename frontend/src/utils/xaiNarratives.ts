import type {
  LocalExplanationResponse,
  GlobalExplanationResponse,
  ForecastExplanationResponse,
} from '../types'
import { formatBusinessValue } from './businessMetrics.ts'

export interface LocalNarrative {
  headline: string
  summaryParagraph: string
  baselineExplanation: string
  topPositiveDrivers: Array<{ feature: string; impactText: string; rawContribution: number; value?: any }>
  topNegativeDrivers: Array<{ feature: string; impactText: string; rawContribution: number; value?: any }>
  scaleDisclosure: string
  attributionDisclaimer: string
}

export interface GlobalNarrative {
  headline: string
  summaryParagraph: string
  topDrivers: Array<{ feature: string; shareText: string; sharePct: number }>
  collinearityNote?: string
}

export interface ForecastNarrative {
  headline: string
  executiveSummary: string
  trendInsight: string
  momentumInsight: string
  intervalReliability: string
  nonCausalDisclosure: string
}

/**
 * Generates human-readable narrative from LocalExplanationResponse.
 */
export function generateLocalNarrative(
  explanation: LocalExplanationResponse | null | undefined,
  targetName: string,
  unit?: string | null
): LocalNarrative | null {
  if (!explanation) return null

  const isLogOdds = explanation.decomposition_space === 'LOG_ODDS_MARGIN'
  const isProbSpace = explanation.decomposition_space === 'PROBABILITY_SPACE'

  // Scale disclosure
  let scaleDisclosure = ''
  if (isLogOdds) {
    scaleDisclosure =
      'Scale Notice: This model uses a logistic/boosted decision margin (log-odds). Contribution values represent directional score adjustments along the decision boundary, not direct percentage point changes in final probability.'
  } else if (isProbSpace) {
    scaleDisclosure =
      'Scale Notice: Feature contributions reflect shifts in ensemble voting probability share across decision trees.'
  } else {
    scaleDisclosure = `Scale Notice: Feature contributions are measured in the original target units (${unit || 'points'}).`
  }

  // Format contribution with appropriate scale/unit
  const formatImpact = (val: number): string => {
    const sign = val > 0 ? '+' : ''
    if (isLogOdds) {
      return `${sign}${val.toFixed(2)} log-odds pts`
    }
    if (isProbSpace) {
      return `${sign}${(val * 100).toFixed(1)}% prob share`
    }
    return `${sign}${formatBusinessValue(val, unit)}`
  }

  // Separate positive and negative drivers
  const positive = explanation.contributions
    .filter((c) => c.contribution > 0.0001)
    .sort((a, b) => b.contribution - a.contribution)
    .map((c) => ({
      feature: c.feature,
      impactText: formatImpact(c.contribution),
      rawContribution: c.contribution,
      value: c.raw_value,
    }))

  const negative = explanation.contributions
    .filter((c) => c.contribution < -0.0001)
    .sort((a, b) => a.contribution - b.contribution)
    .map((c) => ({
      feature: c.feature,
      impactText: formatImpact(c.contribution),
      rawContribution: c.contribution,
      value: c.raw_value,
    }))

  // Baseline explanation
  const baseFormatted = isLogOdds
    ? `${explanation.baseline_reference_value.toFixed(2)} log-odds`
    : isProbSpace
    ? `${(explanation.baseline_reference_value * 100).toFixed(1)}% base share`
    : formatBusinessValue(explanation.baseline_reference_value, unit)

  const baselineExplanation = `The baseline reference point for this model is ${baseFormatted}. This represents the expected outcome when all features are at their training averages or neutral reference states.`

  // Headline & summary paragraph
  let headline = `Prediction Drivers for ${targetName}`
  let summaryParagraph = ''

  const topPos = positive[0]
  const topNeg = negative[0]

  if (topPos && topNeg) {
    summaryParagraph = `The largest factor pushing the prediction higher is "${topPos.feature}" (${topPos.impactText}), while "${topNeg.feature}" (${topNeg.impactText}) provides the strongest downward pressure.`
  } else if (topPos) {
    summaryParagraph = `The prediction is driven primarily upward by "${topPos.feature}" (${topPos.impactText}).`
  } else if (topNeg) {
    summaryParagraph = `The prediction is driven primarily downward by "${topNeg.feature}" (${topNeg.impactText}).`
  } else {
    summaryParagraph = 'Input features are in close alignment with baseline averages, producing an outcome near the reference baseline.'
  }

  const attributionDisclaimer =
    'Statistical Attribution Notice: Feature contributions reflect learned statistical associations and correlation patterns in the training data. They do not constitute proof of causal relationships. Manually altering these input values in real life may not produce the estimated change in outcome.'

  return {
    headline,
    summaryParagraph,
    baselineExplanation,
    topPositiveDrivers: positive,
    topNegativeDrivers: negative,
    scaleDisclosure,
    attributionDisclaimer,
  }
}

/**
 * Generates human-readable narrative from GlobalExplanationResponse.
 */
export function generateGlobalNarrative(
  explanation: GlobalExplanationResponse | null | undefined,
  targetName: string
): GlobalNarrative | null {
  if (!explanation) return null

  const topDrivers = explanation.feature_importances.slice(0, 5).map((fi) => ({
    feature: fi.feature,
    shareText: `${fi.relative_share_pct}% overall impact`,
    sharePct: fi.relative_share_pct,
  }))

  const top1 = topDrivers[0]
  const top2 = topDrivers[1]

  let summaryParagraph = `Across ${explanation.sample_rows_evaluated} analyzed records, `
  if (top1 && top2) {
    summaryParagraph += `the two most influential features determining ${targetName} are "${top1.feature}" (${top1.shareText}) and "${top2.feature}" (${top2.shareText}).`
  } else if (top1) {
    summaryParagraph += `"${top1.feature}" is the single dominant driver (${top1.shareText}).`
  } else {
    summaryParagraph += 'features contribute relatively evenly across the model.'
  }

  let collinearityNote: string | undefined
  if (explanation.correlation_warnings && explanation.correlation_warnings.length > 0) {
    collinearityNote = `Collinearity Notice: ${explanation.correlation_warnings.join('. ')}`
  }

  return {
    headline: `Global Driver Breakdown for ${targetName}`,
    summaryParagraph,
    topDrivers,
    collinearityNote,
  }
}

/**
 * Generates human-readable narrative from ForecastExplanationResponse.
 */
export function generateForecastNarrative(
  explanation: ForecastExplanationResponse | null | undefined,
  metricName: string,
  frequency: string,
  unit?: string | null
): ForecastNarrative | null {
  if (!explanation) return null

  const headline = `Forecast Trajectory for ${metricName}`

  // Trend insight
  const trendDir = explanation.historical_trend.toLowerCase()
  let trendInsight = `Historical data exhibits an overall ${trendDir} trajectory`
  if (explanation.trend_slope !== null && explanation.trend_slope !== undefined) {
    const slopeFormatted = formatBusinessValue(Math.abs(explanation.trend_slope), unit)
    const slopeSign = explanation.trend_slope >= 0 ? 'increasing' : 'declining'
    trendInsight += `, ${slopeSign} at approximately ${slopeFormatted} per ${frequency}.`
  } else {
    trendInsight += ` across observed intervals.`
  }

  // Momentum insight
  let momentumInsight = ''
  if (explanation.recent_change_pct !== null && explanation.recent_change_pct !== undefined) {
    const momPct = explanation.recent_change_pct
    const momSign = momPct >= 0 ? '+' : ''
    momentumInsight = `Recent momentum shifted by ${momSign}${momPct}% leading into the forecast horizon.`
  }

  // Interval reliability
  let intervalReliability = 'Forecast intervals are generated via empirical holdout residuals.'
  if (explanation.empirical_coverage_95) {
    intervalReliability = `Historical backtesting confirms that ${explanation.empirical_coverage_95}% of holdout observations fell within the modeled 95% uncertainty band.`
  }

  // Executive summary
  const executiveSummary = `${explanation.selection_reason || `Projections utilize ${explanation.algorithm} backtested across historical windows.`} ${trendInsight} ${momentumInsight}`.trim()

  const nonCausalDisclosure =
    'Time-Series Projection Notice: Extrapolations are based strictly on chronological patterns and past variations. External shocks, macro shifts, policy changes, and black-swan events not present in historical data cannot be anticipated by univariate time-series algorithms.'

  return {
    headline,
    executiveSummary,
    trendInsight,
    momentumInsight,
    intervalReliability,
    nonCausalDisclosure,
  }
}
