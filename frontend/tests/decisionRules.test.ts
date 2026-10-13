import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatEvidenceValue,
  getPriorityBadgeInfo,
  getStatusBadgeInfo,
  requiresStatusComment,
  isTerminalStatus,
  validateRuleForm,
  canTransitionTo,
  formatComparisonRule,
  getRecommendationCounts,
} from '../src/utils/decisionUtils.ts'
import type { Recommendation } from '../src/types/decisionTypes.ts'

test('formatEvidenceValue handles various types, numbers, and units', () => {
  assert.equal(formatEvidenceValue(null), 'N/A')
  assert.equal(formatEvidenceValue(undefined), 'N/A')
  assert.equal(formatEvidenceValue(true), 'True')
  assert.equal(formatEvidenceValue(false), 'False')
  assert.equal(formatEvidenceValue(1500, '$'), '$1,500')
  assert.equal(formatEvidenceValue(25.4, '%'), '25.4%')
  assert.equal(formatEvidenceValue(14, 'days'), '14 days')
  assert.equal(formatEvidenceValue(100, 'units'), '100 units')
  assert.equal(formatEvidenceValue('high_risk'), 'high_risk')
})

test('getPriorityBadgeInfo returns correct badges and styles', () => {
  const critical = getPriorityBadgeInfo('critical')
  assert.equal(critical.label, 'Critical')
  assert.ok(critical.bg.includes('rose'))

  const high = getPriorityBadgeInfo('high')
  assert.equal(high.label, 'High')
  assert.ok(high.bg.includes('amber'))

  const medium = getPriorityBadgeInfo('medium')
  assert.equal(medium.label, 'Medium')
  assert.ok(medium.bg.includes('blue'))

  const low = getPriorityBadgeInfo('low')
  assert.equal(low.label, 'Low')

  const info = getPriorityBadgeInfo('informational')
  assert.equal(info.label, 'Info')
})

test('getStatusBadgeInfo returns correct statuses and descriptions', () => {
  const review = getStatusBadgeInfo('needs_review')
  assert.equal(review.label, 'Needs Review')

  const approved = getStatusBadgeInfo('approved')
  assert.equal(approved.label, 'Approved')

  const rejected = getStatusBadgeInfo('rejected')
  assert.equal(rejected.label, 'Rejected')

  const completed = getStatusBadgeInfo('completed')
  assert.equal(completed.label, 'Completed')

  const dismissed = getStatusBadgeInfo('dismissed')
  assert.equal(dismissed.label, 'Dismissed')
})

test('requiresStatusComment strictly enforces comments on rejected and dismissed', () => {
  assert.equal(requiresStatusComment('rejected'), true)
  assert.equal(requiresStatusComment('dismissed'), true)
  assert.equal(requiresStatusComment('approved'), false)
  assert.equal(requiresStatusComment('needs_review'), false)
  assert.equal(requiresStatusComment('pending_approval'), false)
  assert.equal(requiresStatusComment('completed'), false)
})

test('isTerminalStatus accurately identifies final states', () => {
  assert.equal(isTerminalStatus('completed'), true)
  assert.equal(isTerminalStatus('rejected'), true)
  assert.equal(isTerminalStatus('dismissed'), true)
  assert.equal(isTerminalStatus('needs_review'), false)
  assert.equal(isTerminalStatus('pending_approval'), false)
  assert.equal(isTerminalStatus('approved'), false)
})

test('canTransitionTo enforces proper decision review workflow', () => {
  // From needs_review
  assert.equal(canTransitionTo('needs_review', 'approved'), true)
  assert.equal(canTransitionTo('needs_review', 'rejected'), true)
  assert.equal(canTransitionTo('needs_review', 'dismissed'), true)
  assert.equal(canTransitionTo('needs_review', 'completed'), false) // Must be approved first!

  // From approved
  assert.equal(canTransitionTo('approved', 'completed'), true)
  assert.equal(canTransitionTo('approved', 'dismissed'), true)
  assert.equal(canTransitionTo('approved', 'rejected'), true)

  // From completed (reopening)
  assert.equal(canTransitionTo('completed', 'needs_review'), true)
  assert.equal(canTransitionTo('completed', 'approved'), false)

  // Same status transition is false
  assert.equal(canTransitionTo('approved', 'approved'), false)
})

test('formatComparisonRule creates readable formula representations', () => {
  assert.equal(
    formatComparisonRule({
      field_name: 'available_inventory',
      operator: 'lt',
      threshold_value: 100,
      expected_unit: 'units',
    }),
    'available_inventory < 100 units'
  )

  assert.equal(
    formatComparisonRule({
      field_name: 'predicted_demand',
      operator: 'gt',
      compare_to_field: 'max_capacity',
    }),
    'predicted_demand > field:max_capacity'
  )

  assert.equal(
    formatComparisonRule({
      field_name: 'feature_timestamp',
      operator: 'is_missing',
    }),
    'feature_timestamp is missing'
  )

  assert.equal(
    formatComparisonRule({
      field_name: 'model_score',
      operator: 'is_present',
    }),
    'model_score is present'
  )
})

test('getRecommendationCounts aggregates all lifecycle states accurately', () => {
  const dummyRecs = [
    { status: 'needs_review' },
    { status: 'needs_review' },
    { status: 'pending_approval' },
    { status: 'approved' },
    { status: 'completed' },
    { status: 'rejected' },
    { status: 'dismissed' },
  ] as Recommendation[]

  const counts = getRecommendationCounts(dummyRecs)
  assert.equal(counts.total, 7)
  assert.equal(counts.needsReview, 2)
  assert.equal(counts.pendingApproval, 1)
  assert.equal(counts.awaitingAction, 3)
  assert.equal(counts.approved, 1)
  assert.equal(counts.completed, 1)
  assert.equal(counts.rejected, 1)
  assert.equal(counts.dismissed, 1)
})

test('validateRuleForm catches missing fields and invalid operators', () => {
  // Empty form
  const emptyRes = validateRuleForm({})
  assert.equal(emptyRes.isValid, false)
  assert.ok(emptyRes.errors.length >= 4)

  // Missing threshold/compare field for gt
  const partialRes = validateRuleForm({
    name: 'Test Rule',
    scenario: 'inventory',
    field_name: 'available_inventory',
    operator: 'gt',
    recommended_action: 'Alert staff',
  })
  assert.equal(partialRes.isValid, false)
  assert.ok(partialRes.errors.some((e) => e.includes("Operator 'gt' requires either a Threshold Value")))

  // Valid with threshold
  const validThreshold = validateRuleForm({
    name: 'Stock Alert',
    scenario: 'inventory',
    field_name: 'available_inventory',
    operator: 'lt',
    threshold_value: 50,
    recommended_action: 'Order inventory',
  })
  assert.equal(validThreshold.isValid, true)
  assert.equal(validThreshold.errors.length, 0)

  // Valid with compare_to_field
  const validCompare = validateRuleForm({
    name: 'Below Safety Stock',
    scenario: 'inventory',
    field_name: 'available_inventory',
    operator: 'lt',
    compare_to_field: 'safety_stock',
    recommended_action: 'Reorder now',
  })
  assert.equal(validCompare.isValid, true)
  assert.equal(validCompare.errors.length, 0)

  // Valid unary operator (is_missing)
  const validUnary = validateRuleForm({
    name: 'Missing Price',
    scenario: 'data_quality',
    field_name: 'unit_price',
    operator: 'is_missing',
    recommended_action: 'Flag record',
  })
  assert.equal(validUnary.isValid, true)
  assert.equal(validUnary.errors.length, 0)
})
