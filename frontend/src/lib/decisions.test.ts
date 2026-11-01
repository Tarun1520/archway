import { describe, expect, it } from 'vitest'
import type { DecisionReceipt } from './api/types'
import type { EligibilityVerdict } from './api/types'
import { decidedByModel, describeReceipt, engineOf, engineOfReceipts, receiptsById, summarise, totals } from './decisions'

const receipt = (over: Partial<DecisionReceipt>): DecisionReceipt => ({
  id: Math.random().toString(),
  candidate_id: 'c1',
  requirement_id: null,
  question_type: 'requirement_fit',
  rubric_version: 'r',
  jev_mode: 'live',
  jev_model_id: 'typesafe-ai/jev',
  reported_confidence: 0.9,
  final_result: 'meets',
  aggregation_policy: null,
  needs_review: false,
  ...over,
})

describe('summarise', () => {
  it('words the answers and keeps the mode', () => {
    const s = summarise([
      receipt({ requirement_id: 'REQ-2', final_result: 'clearly_meets' }),
      receipt({ question_type: 'integration_risk', final_result: 'low' }),
      receipt({ question_type: 'needs_human_review', final_result: 'no' }),
    ])
    expect(s).toMatchObject({
      fit: ['clearly meets REQ-2'], risk: 'low', review: 'no', mode: 'live', engine: 'typesafe-ai/jev', evaluated: true, needsReview: false,
    })
    expect(s?.lines.map((l) => l.question)).toEqual(['Fit to REQ-2', 'Integration risk', 'Needs a person to look'])
  })

  it('says "not evaluated" plainly when nothing was answered', () => {
    const s = summarise([receipt({ final_result: null, needs_review: true })])
    expect(s?.evaluated).toBe(false)
    expect(s?.needsReview).toBe(true)
  })

  it('groups receipts by component', () => {
    const grouped = receiptsById([receipt({}), receipt({ candidate_id: 'c2' }), receipt({})])
    expect(grouped.get('c1')).toHaveLength(2)
  })
})


describe('who answered', () => {
  it('names Laya for what it is, and never calls it Jev', () => {
    const laya = engineOf('laya/typed-decisions', 'live')
    expect(laya.id).toBe('laya')
    expect(laya.label).toBe('LAYA')
    expect(laya.detail).toMatch(/not Jev/i)
    expect(engineOf('laya-rl-agent', 'live').id).toBe('laya') // the id the running service really reports
    expect(engineOf('typesafe-ai/jev', 'live').id).toBe('jev')
    expect(engineOf(null, 'fixture').id).toBe('fixture')
    expect(engineOf(null, 'live').id).toBe('none')
  })

  it('reads the engine from the first receipt that actually answered', () => {
    const none = receipt({ jev_model_id: null, final_result: null })
    const laya = receipt({ jev_model_id: 'laya/typed-decisions' })
    expect(engineOfReceipts([none, laya]).id).toBe('laya')
    expect(engineOfReceipts([none]).id).toBe('none')
    expect(summarise([none, laya])?.source.label).toBe('LAYA')
  })

  it('words each question and keeps "not asked" as null, never a guess', () => {
    expect(describeReceipt(receipt({ requirement_id: 'REQ-1', final_result: 'partially_meets', reported_confidence: 0.7 }))).toEqual({
      question: 'Fit to REQ-1', answer: 'partially meets', confidence: 0.7, needsReview: false,
    })
    expect(describeReceipt(receipt({ question_type: 'integration_risk', final_result: 'high' })).answer).toBe('high risk')
    expect(describeReceipt(receipt({ final_result: null, needs_review: true })).answer).toBeNull()
  })
})

describe('rules versus the decision model', () => {
  const verdict = (over: Partial<EligibilityVerdict>): EligibilityVerdict => ({
    component_id: 'c1', status: 'eligible', reasons: [], policy_version: 'p', ...over,
  })

  it('says the model decided only when its answer did', () => {
    expect(decidedByModel(verdict({ decided_by: 'decision_model', status: 'unresolved', reasons: ['x'] }))).toBe(true)
    expect(decidedByModel(verdict({ decided_by: 'rules', status: 'excluded', reasons: ['license'] }))).toBe(false)
    expect(decidedByModel(null)).toBe(false)
  })

  it('recognises the model-made reason in verdicts saved before decided_by existed', () => {
    const old = verdict({ status: 'unresolved', reasons: ['the decision model judged that the evidence does not show it meets the requirement'] })
    expect(decidedByModel(old)).toBe(true)
    expect(decidedByModel(verdict({ status: 'excluded', reasons: ['the repository is archived'] }))).toBe(false)
  })

  it('splits a run between rules and the model, and counts what could not be asked', () => {
    const t = totals(
      [verdict({}), verdict({ component_id: 'c2', status: 'unresolved', reasons: ['x'], decided_by: 'decision_model' })],
      [receipt({ jev_model_id: 'laya/typed-decisions' }), receipt({ final_result: null, jev_model_id: null })],
    )
    expect(t).toMatchObject({ components: 2, byRules: 1, byModel: 1, answered: 1, notAsked: 1 })
    expect(t.engine.id).toBe('laya')
  })
})
