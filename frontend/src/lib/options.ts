/**
 * Helpers for the Options step: which versions are on offer, what phase the step is in, and the words for
 * the comparison table. Plain functions over the saved snapshots, so the screen can only show what is saved.
 */
import type { ArchitectureOption, Dimension, OptionsSnapshot, Rating, RunSnapshot } from './api/types'

export const DIMENSION_LABEL: Record<Dimension, string> = {
  simplicity: 'Simplicity',
  effort: 'Implementation effort',
  oss_reuse: 'Open-source reuse',
  integration_risk: 'Integration risk',
  maintainability: 'Maintainability',
  privacy: 'Privacy',
  cost_exposure: 'Cost exposure',
  evidence_coverage: 'Evidence coverage',
}

/** "Favourable" is always the good end, whatever the row: simple, light, private, cheap, well supported. */
export const RATING_LABEL: Record<Rating, string> = { good: 'Favourable', mixed: 'Mixed', poor: 'Unfavourable', unknown: 'Not assessed' }

export const DIMENSION_ORDER = Object.keys(DIMENSION_LABEL) as Dimension[]

export type OptionsPhase =
  | 'none' // not asked for
  | 'drafting' // the model is drafting or reviewing
  | 'choosing' // waiting for the person to pick or ask for a change
  | 'no_recommendation' // nothing could honestly be recommended
  | 'approving' // one version is selected, waiting for approval
  | 'approved' // one version approved
  | 'stopped' // drafting stopped on an error

export function optionsPhase(run: RunSnapshot | null, options: OptionsSnapshot | null): OptionsPhase {
  const waiting = run?.waiting_for
  if (run?.running) return 'drafting' // working always wins: a pause it already left can still be in the snapshot
  if (waiting?.node === 'select_or_revise') return waiting.payload.no_recommendation ? 'no_recommendation' : 'choosing'
  if (waiting?.node === 'approve_version') return 'approving'
  if (options?.approved && run?.finished) return 'approved'
  if (options?.requested) return run?.finished ? 'approved' : 'stopped'
  return 'none'
}

/** The versions on offer: for each option, its newest version that passed review. */
export function presentedOptions(options: OptionsSnapshot | null): ArchitectureOption[] {
  if (!options) return []
  return options.presented
    .map((ref) => options.options.find((o) => o.id === ref.id && o.version === ref.version))
    .filter((o): o is ArchitectureOption => o !== undefined)
}

/** Every saved version of one option, oldest first. */
export function versionsOf(options: OptionsSnapshot | null, id: string): ArchitectureOption[] {
  return (options?.options ?? []).filter((o) => o.id === id).sort((a, b) => a.version - b.version)
}

/** Options (newest version) that were drafted but did not pass review, so were not offered. */
export function withheld(options: OptionsSnapshot | null): ArchitectureOption[] {
  if (!options) return []
  const newest = new Map<string, ArchitectureOption>()
  for (const option of options.options) {
    const seen = newest.get(option.id)
    if (!seen || option.version > seen.version) newest.set(option.id, option)
  }
  return [...newest.values()].filter((o) => o.review && !o.review.passed && !options.presented.some((p) => p.id === o.id))
}

export function versionLabel(option: { id: string; version: number }): string {
  return `${option.id} · version ${option.version}`
}

/** Warnings worth showing on a card (the blocking ones never reach a presented option). */
export function warnings(option: ArchitectureOption) {
  return (option.review?.issues ?? []).filter((issue) => issue.severity === 'warning')
}

/** Counts for the card's header strip. */
export function mix(option: ArchitectureOption): { reuse: number; build: number } {
  return {
    reuse: option.components.filter((c) => c.kind === 'reuse').length,
    build: option.components.filter((c) => c.kind === 'build').length,
  }
}
