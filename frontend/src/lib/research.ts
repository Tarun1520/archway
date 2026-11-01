/**
 * Reading research records the way a person should see them.
 *
 * The backend keeps three kinds of "no license" apart (see license_state in
 * backend/app/models/evidence.py), because they mean different things for
 * the eligibility rules in the next phase:
 *
 *   detected        a license was found (e.g. "MIT")
 *   none_detected   GitHub looked and found no license file
 *   not_retrieved   we could not find out (the request failed)
 *
 * This file names those states in one place, with the wording shown to the
 * user, so every card says the same thing.
 */
import type { AgentName, ComponentCandidate, LicenseStatus, SourceFacts } from './api/types'

export interface LicenseView {
  kind: LicenseStatus
  label: string
}

/** The license as a person should read it. The status comes from the backend's facts. */
export function licenseView(facts: Pick<SourceFacts, 'license' | 'license_status' | 'kind'>): LicenseView {
  switch (facts.license_status) {
    case 'detected':
      return { kind: 'detected', label: facts.license ?? 'Detected' }
    case 'unrecognised':
      return { kind: 'unrecognised', label: 'License not recognised' }
    case 'none_detected':
      return { kind: 'none_detected', label: facts.kind === 'github' ? 'No license detected' : 'No license declared' }
    default:
      return { kind: 'not_retrieved', label: 'License not retrieved' }
  }
}

const AGENT_LABELS: Record<AgentName | 'team', string> = {
  research_lead: 'Research lead',
  capability_analyst: 'Capability analyst',
  component_scout: 'Component scout',
  project_scout: 'Project scout',
  reviewer: 'Reviewer',
  relevance_judge: 'Relevance judge',
  team: 'Team',
}

export function agentLabel(name: string): string {
  return AGENT_LABELS[name as AgentName] ?? name
}

/** "not retrieved" when we tried and failed, "not reported" when GitHub simply has no value. */
export function absenceWord(field: string, missingFields: string[]): string {
  return missingFields.includes(field) ? 'not retrieved' : 'not reported'
}

const SOURCE_LABELS: Record<string, string> = {
  repo_metadata: 'Repository details',
  readme: 'README',
  linked_doc: 'Linked documentation',
  user_url: 'Address you supplied',
  package_registry: 'Package registry',
}

export function sourceLabel(sourceType: string): string {
  return SOURCE_LABELS[sourceType] ?? sourceType
}

/** A date and time in UTC, so it reads the same everywhere. */
export function formatWhen(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return (
    new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(date) + ' UTC'
  )
}

/** Only addresses that start with https:// are turned into links. */
export function safeHref(url: string): string | null {
  return /^https:\/\//i.test(url) ? url : null
}

export function shortHash(hash: string | null): string | null {
  return hash ? hash.slice(0, 12) : null
}

// --- Relevance (the independent judge's verdict) ------------------------------------

const FIT_LABELS: Record<number, string> = { 3: 'Direct fit', 2: 'Partial fit', 1: 'Reference only' }
const KIND_LABELS: Record<NonNullable<ComponentCandidate['kind']>, string> = {
  building_block: 'Library or package',
  framework: 'Framework',
  service: 'Service to run',
  reference_app: 'Finished app or demo',
}

/** Words for a component's judged fit, or null when it was not assessed. */
export function fitView(component: ComponentCandidate): { label: string; kind: string | null } | null {
  if (component.fit === null) return null
  return { label: FIT_LABELS[component.fit] ?? 'Not assessed', kind: component.kind ? KIND_LABELS[component.kind] : null }
}

/**
 * Whether a component counts as a building block for its approach. A
 * "reference only" component is kept (it may be worth studying) but is shown
 * apart and does not count as covering an approach. Not assessed counts, so
 * older research is unchanged.
 */
export function isBuildingBlock(component: ComponentCandidate): boolean {
  return component.fit === null || component.fit >= 2
}

/**
 * A rough, comparable measure of how much a source is used: GitHub stars and
 * registry downloads are on different scales, so a star counts as 50 monthly
 * downloads. Only used to order equally relevant options, never to judge fit.
 */
export function adoptionWeight(facts: SourceFacts): number {
  return Math.max((facts.stars ?? 0) * 50, facts.downloads_last_month ?? 0)
}

/** Low adoption: known, and small (under 10 stars, or under 500 downloads a month). Unknown is not "low". */
export function isLowAdoption(facts: SourceFacts): boolean {
  if (facts.kind === 'github') return facts.stars !== null && facts.stars < 10
  return facts.downloads_last_month != null && facts.downloads_last_month < 500
}

/** "2.4M", "95k", "812": short counts for small labels. */
export function shortCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`
  return String(value)
}

/** Best fit first, then the more adopted; stable for equal ones. */
export function byRelevance(a: ComponentCandidate, b: ComponentCandidate): number {
  const fit = (b.fit ?? 2) - (a.fit ?? 2)
  if (fit !== 0) return fit
  return adoptionWeight(b.facts) - adoptionWeight(a.facts)
}

/** A capability name for people: "idea_input_collection" -> "idea input collection". */
export function capabilityTitle(name: string): string {
  return name.replace(/_/g, ' ').replace(/\s+/g, ' ').trim()
}
