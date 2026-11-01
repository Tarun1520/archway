/**
 * Small helpers that turn Phase 4 verdicts and receipts into words for the screen.
 *
 * WHO DECIDED WHAT is shown everywhere a decision appears:
 *   RULES   plain code (the eligibility gate: license, archived, finished apps). Always has the last word.
 *   LAYA    the open-source decision model that answers short questions about each component (fit to a
 *           requirement, integration risk, whether a person should look). It is named for what answered:
 *           never "Jev", which would be a different service.
 */
import type { DecisionReceipt, EligibilityStatus, EligibilityVerdict, ServiceMode } from './api/types'

export const ELIGIBILITY_LABEL: Record<EligibilityStatus, string> = {
  eligible: 'Eligible',
  review_required: 'Review needed',
  unresolved: 'Unresolved',
  excluded: 'Excluded',
}

/** The gate's order: an eligible component always sorts first (the invariant). */
export const ELIGIBILITY_TIER: Record<EligibilityStatus, number> = { eligible: 0, review_required: 1, unresolved: 2, excluded: 3 }

const FIT_WORDS: Record<string, string> = {
  does_not_meet: 'does not meet',
  partially_meets: 'partially meets',
  meets: 'meets',
  clearly_meets: 'clearly meets',
}

// --- Who answered ----------------------------------------------------------------------------

export type EngineId = 'laya' | 'jev' | 'fixture' | 'other' | 'none'

export interface DecisionEngine {
  id: EngineId
  /** The short name for a badge: LAYA, JEV, FIXTURE. */
  label: string
  /** One sentence for a tooltip. */
  detail: string
}

const NO_ENGINE: DecisionEngine = { id: 'none', label: 'NOT ASKED', detail: 'The decision model was not asked, or could not answer: nothing was guessed.' }

/** Names the engine from the model id a receipt carries ("laya/typed-decisions") and whether the call was live or a fixture. */
export function engineOf(modelId: string | null | undefined, mode: ServiceMode | null | undefined): DecisionEngine {
  const id = (modelId ?? '').toLowerCase()
  if (id.startsWith('laya')) {
    return {
      id: 'laya',
      label: 'LAYA',
      detail: `Answered by Laya (${modelId}), an open-source decision model running on this computer. Not Jev.`,
    }
  }
  if (mode === 'fixture') return { id: 'fixture', label: 'FIXTURE', detail: 'A fixed sample answer, not a real model. Used for tests and offline demos.' }
  if (id.includes('jev')) return { id: 'jev', label: 'JEV', detail: `Answered by ${modelId}.` }
  if (id) return { id: 'other', label: id.toUpperCase(), detail: `Answered by ${modelId}.` }
  return NO_ENGINE
}

/** The engine behind a component's receipts (the first one that actually answered). */
export function engineOfReceipts(receipts: DecisionReceipt[]): DecisionEngine {
  const answered = receipts.find((r) => r.jev_model_id) ?? receipts[0]
  return answered ? engineOf(answered.jev_model_id, answered.jev_mode) : NO_ENGINE
}

/** Did the decision model's answer (rather than a plain rule) decide this component's eligibility? */
export function decidedByModel(verdict: EligibilityVerdict | null | undefined): boolean {
  if (!verdict) return false
  // Older saved verdicts have no `decided_by`: their one model-made reason is recognised by its words.
  return verdict.decided_by === 'decision_model' || (verdict.decided_by === undefined && verdict.reasons.some((r) => r.startsWith('the decision model judged')))
}

// --- One component's decisions -----------------------------------------------------------------

export interface DecisionLine {
  /** What was asked, in words: "Fit to REQ-1", "Integration risk", "Needs a person to look". */
  question: string
  /** The answer, or null when it could not be asked (never a guess). */
  answer: string | null
  /** How sure the model said it was, 0 to 1 (the model's own figure, not correctness). */
  confidence: number | null
  needsReview: boolean
}

export interface DecisionSummary {
  /** e.g. "clearly meets REQ-2", one per requirement asked about. */
  fit: string[]
  risk: string | null
  review: string | null
  /** Live or fixture, shown on every summary so a fixture answer is never mistaken for a real one. */
  mode: string
  /** The engine that answered, e.g. "laya/typed-decisions": a substitute is never shown as Jev. */
  engine: string | null
  /** The same, as something a badge can show. */
  source: DecisionEngine
  evaluated: boolean
  needsReview: boolean
  /** Every question with its answer, for the full list. */
  lines: DecisionLine[]
}

export function describeReceipt(receipt: DecisionReceipt): DecisionLine {
  const answer = receipt.final_result
  if (receipt.question_type === 'requirement_fit') {
    return {
      question: `Fit to ${receipt.requirement_id ?? 'the requirement'}`,
      answer: answer ? (FIT_WORDS[answer] ?? answer) : null,
      confidence: receipt.reported_confidence,
      needsReview: receipt.needs_review,
    }
  }
  if (receipt.question_type === 'integration_risk') {
    return { question: 'Integration risk', answer: answer ? `${answer} risk` : null, confidence: receipt.reported_confidence, needsReview: receipt.needs_review }
  }
  return { question: 'Needs a person to look', answer: answer ?? null, confidence: receipt.reported_confidence, needsReview: receipt.needs_review }
}

export function summarise(receipts: DecisionReceipt[]): DecisionSummary | null {
  if (receipts.length === 0) return null
  const fit = receipts
    .filter((r) => r.question_type === 'requirement_fit' && r.final_result)
    .map((r) => `${FIT_WORDS[r.final_result as string] ?? r.final_result}${r.requirement_id ? ` ${r.requirement_id}` : ''}`)
  const risk = receipts.find((r) => r.question_type === 'integration_risk')?.final_result ?? null
  const review = receipts.find((r) => r.question_type === 'needs_human_review')?.final_result ?? null
  return {
    fit,
    risk,
    review,
    mode: receipts[0].jev_mode,
    engine: receipts.find((r) => r.jev_model_id)?.jev_model_id ?? null,
    source: engineOfReceipts(receipts),
    evaluated: receipts.some((r) => r.final_result !== null),
    needsReview: receipts.some((r) => r.needs_review),
    lines: receipts.map(describeReceipt),
  }
}

/** How the decisions of a whole run split between the rules and the decision model. */
export interface DecisionTotals {
  components: number
  /** Components whose eligibility the plain rules decided. */
  byRules: number
  /** Components where the decision model's answer decided it. */
  byModel: number
  /** Questions the model answered, and ones it could not be asked. */
  answered: number
  notAsked: number
  engine: DecisionEngine
}

export function totals(verdicts: EligibilityVerdict[], receipts: DecisionReceipt[]): DecisionTotals {
  const byModel = verdicts.filter(decidedByModel).length
  return {
    components: verdicts.length,
    byRules: verdicts.length - byModel,
    byModel,
    answered: receipts.filter((r) => r.final_result !== null).length,
    notAsked: receipts.filter((r) => r.final_result === null).length,
    engine: engineOfReceipts(receipts),
  }
}

export function verdictsById(verdicts: EligibilityVerdict[]): Map<string, EligibilityVerdict> {
  return new Map(verdicts.map((v) => [v.component_id, v]))
}

export function receiptsById(receipts: DecisionReceipt[]): Map<string, DecisionReceipt[]> {
  const byId = new Map<string, DecisionReceipt[]>()
  for (const receipt of receipts) byId.set(receipt.candidate_id, [...(byId.get(receipt.candidate_id) ?? []), receipt])
  return byId
}
