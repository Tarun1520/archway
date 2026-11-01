/**
 * Turning a stored brief into an editable copy, and back into an edit request.
 *
 * WHY IDS MATTER
 *   Each requirement has a stable id (REQ-1, REQ-2 ...). Later phases attach
 *   evidence and decisions to those ids. So when a requirement is only
 *   reworded, its id is kept; a newly added one is sent WITHOUT an id and the
 *   backend gives it the next free one.
 */
import type { BriefEdit, EditedItem, ProjectBrief } from './api/types'

/** One editable row. `key` is only for React's list rendering. */
export interface DraftItem {
  key: string
  id?: string
  text: string
}

export interface BriefDraft {
  problem: string
  users: string
  mustHave: DraftItem[]
  niceToHave: DraftItem[]
  budget: string
  privacy: string
  deployment: string
  stated: DraftItem[]
  assumptions: DraftItem[]
  unknowns: DraftItem[]
  stack: DraftItem[]
}

let nextKey = 0
export function newItem(text = '', id?: string): DraftItem {
  nextKey += 1
  return { key: `item-${nextKey}`, id, text }
}

export function draftFromBrief(brief: ProjectBrief): BriefDraft {
  return {
    problem: brief.problem,
    users: brief.users ?? '',
    mustHave: brief.must_have.map((item) => newItem(item.text, item.id)),
    niceToHave: brief.nice_to_have.map((item) => newItem(item.text, item.id)),
    budget: brief.constraints.budget ?? '',
    privacy: brief.constraints.privacy ?? '',
    deployment: brief.constraints.deployment ?? '',
    stated: brief.constraints.stated.map((text) => newItem(text)),
    assumptions: brief.assumptions.map((item) => newItem(item.text, item.id)),
    unknowns: brief.unknowns.map((text) => newItem(text)),
    stack: brief.stack_preferences.map((text) => newItem(text)),
  }
}

/** An empty box means "not stated", which is sent as null, never as "". */
function textOrNull(value: string): string | null {
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

function withIds(items: DraftItem[]): EditedItem[] {
  return items
    .filter((item) => item.text.trim() !== '') // a row left blank is dropped
    .map((item) => (item.id ? { id: item.id, text: item.text.trim() } : { text: item.text.trim() }))
}

function texts(items: DraftItem[]): string[] {
  return items.map((item) => item.text.trim()).filter((text) => text !== '')
}

export function editFromDraft(draft: BriefDraft): BriefEdit {
  return {
    problem: draft.problem.trim(),
    users: textOrNull(draft.users),
    must_have: withIds(draft.mustHave),
    nice_to_have: withIds(draft.niceToHave),
    stack_preferences: texts(draft.stack),
    constraints: {
      budget: textOrNull(draft.budget),
      privacy: textOrNull(draft.privacy),
      deployment: textOrNull(draft.deployment),
      stated: texts(draft.stated),
    },
    assumptions: withIds(draft.assumptions),
    unknowns: texts(draft.unknowns),
  }
}

// --- Adding suggestions to a draft --------------------------------------------
//
// A suggestion is the model's idea. It becomes part of the brief only when the
// user chooses it, and these functions are how it gets in: each one returns a
// NEW draft and never touches the saved brief. The user can still edit or
// remove anything that was added.

function normalise(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim()
}

function has(items: DraftItem[], text: string): boolean {
  const wanted = normalise(text)
  return items.some((item) => normalise(item.text) === wanted)
}

/** True when the draft differs from the saved brief. */
export function isDirty(draft: BriefDraft, brief: ProjectBrief): boolean {
  return JSON.stringify(editFromDraft(draft)) !== JSON.stringify(editFromDraft(draftFromBrief(brief)))
}

export function addMustHave(draft: BriefDraft, text: string): BriefDraft {
  return has(draft.mustHave, text) ? draft : { ...draft, mustHave: [...draft.mustHave, newItem(text)] }
}

export function addAssumption(draft: BriefDraft, text: string): BriefDraft {
  return has(draft.assumptions, text) ? draft : { ...draft, assumptions: [...draft.assumptions, newItem(text)] }
}

/** Budget, privacy and deployment hold one value; "stated" is a list of sentences. */
export function setConstraint(draft: BriefDraft, field: 'budget' | 'privacy' | 'deployment' | 'stated', text: string): BriefDraft {
  if (field === 'stated') {
    return has(draft.stated, text) ? draft : { ...draft, stated: [...draft.stated, newItem(text)] }
  }
  return { ...draft, [field]: text }
}

/**
 * An open question gets an answer. The answer is added where it belongs, and
 * the question is removed from "still unknown" because it is no longer unknown.
 */
export function resolveUnknown(
  draft: BriefDraft,
  unknownKey: string,
  answer: string,
  addAs: 'must_have' | 'assumption',
): BriefDraft {
  const withoutQuestion = { ...draft, unknowns: draft.unknowns.filter((item) => item.key !== unknownKey) }
  return addAs === 'must_have' ? addMustHave(withoutQuestion, answer) : addAssumption(withoutQuestion, answer)
}

/** True when a suggestion's text is already in the given rows (so it is not offered again). */
export function alreadyIn(items: DraftItem[], text: string): boolean {
  return has(items, text)
}

export function addNiceToHave(draft: BriefDraft, text: string): BriefDraft {
  return has(draft.niceToHave, text) ? draft : { ...draft, niceToHave: [...draft.niceToHave, newItem(text)] }
}

export function addStack(draft: BriefDraft, text: string): BriefDraft {
  return has(draft.stack, text) ? draft : { ...draft, stack: [...draft.stack, newItem(text)] }
}
