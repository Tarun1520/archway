import { describe, expect, it } from 'vitest'
import type { ProjectBrief } from './api/types'
import {
  addAssumption,
  addMustHave,
  alreadyIn,
  draftFromBrief,
  editFromDraft,
  isDirty,
  newItem,
  resolveUnknown,
  setConstraint,
} from './briefEdit'

const brief: ProjectBrief = {
  id: 'brief-1',
  version: 2,
  problem: 'A team wiki',
  users: null,
  must_have: [
    { id: 'REQ-1', text: 'Pages are markdown' },
    { id: 'REQ-2', text: 'Page history' },
  ],
  nice_to_have: [],
  stack_preferences: [],
  constraints: { budget: null, privacy: null, deployment: 'Local', stated: ['No paid hosting.'] },
  assumptions: [{ id: 'ASM-users', text: 'One person uses it.', reason: 'You skipped the question.' }],
  unknowns: ['How many pages'],
  conflicts: [],
  confirmed: false,
}

describe('brief editing', () => {
  it('round-trips a brief without changing its meaning', () => {
    expect(editFromDraft(draftFromBrief(brief))).toEqual({
      problem: 'A team wiki',
      users: null,
      must_have: [
        { id: 'REQ-1', text: 'Pages are markdown' },
        { id: 'REQ-2', text: 'Page history' },
      ],
      nice_to_have: [],
      stack_preferences: [],
      constraints: { budget: null, privacy: null, deployment: 'Local', stated: ['No paid hosting.'] },
      assumptions: [{ id: 'ASM-users', text: 'One person uses it.' }],
      unknowns: ['How many pages'],
    })
  })

  it('keeps the id of a reworded item and sends a new item without one', () => {
    const draft = draftFromBrief(brief)
    draft.mustHave[0].text = 'Pages are written in markdown'
    draft.mustHave.push(newItem('Search'))

    expect(editFromDraft(draft).must_have).toEqual([
      { id: 'REQ-1', text: 'Pages are written in markdown' },
      { id: 'REQ-2', text: 'Page history' },
      { text: 'Search' },
    ])
  })

  it('sends an emptied box as null and drops blank rows', () => {
    const draft = draftFromBrief(brief)
    draft.deployment = '   '
    draft.mustHave[1].text = ''

    const edit = editFromDraft(draft)
    expect(edit.constraints.deployment).toBeNull()
    expect(edit.must_have).toEqual([{ id: 'REQ-1', text: 'Pages are markdown' }])
  })
})


describe('adding suggestions to a draft', () => {
  it('adds a suggestion as a new requirement without an id, and never twice', () => {
    const once = addMustHave(draftFromBrief(brief), 'Search across pages')
    const twice = addMustHave(once, '  search across   pages ')
    expect(editFromDraft(twice).must_have).toEqual([
      { id: 'REQ-1', text: 'Pages are markdown' },
      { id: 'REQ-2', text: 'Page history' },
      { text: 'Search across pages' },
    ])
  })

  it('sets a single-value constraint and appends a stated limit', () => {
    let draft = setConstraint(draftFromBrief(brief), 'budget', 'No paid hosting tiers')
    draft = setConstraint(draft, 'stated', 'Card data never touches our server')
    const edit = editFromDraft(draft)
    expect(edit.constraints.budget).toBe('No paid hosting tiers')
    expect(edit.constraints.stated).toEqual(['No paid hosting.', 'Card data never touches our server'])
  })

  it('answers an unknown: the answer is added and the question is removed', () => {
    const draft = draftFromBrief(brief)
    const question = draft.unknowns[0]
    const answered = resolveUnknown(draft, question.key, 'Pages are limited to a few hundred', 'assumption')
    const edit = editFromDraft(answered)
    expect(edit.unknowns).toEqual([])
    expect(edit.assumptions.map((item) => item.text)).toEqual(['One person uses it.', 'Pages are limited to a few hundred'])
  })

  it('an answer that is a requirement goes to must have', () => {
    const draft = draftFromBrief(brief)
    const answered = resolveUnknown(draft, draft.unknowns[0].key, 'Supports up to a few hundred pages', 'must_have')
    expect(editFromDraft(answered).must_have.at(-1)).toEqual({ text: 'Supports up to a few hundred pages' })
  })

  it('knows when the draft differs from the saved brief', () => {
    const draft = draftFromBrief(brief)
    expect(isDirty(draft, brief)).toBe(false)
    expect(isDirty(addAssumption(draft, 'Hosted on one server'), brief)).toBe(true)
  })

  it('recognises text that is already in a list, ignoring case and spacing', () => {
    expect(alreadyIn(draftFromBrief(brief).mustHave, 'PAGE   history')).toBe(true)
    expect(alreadyIn(draftFromBrief(brief).mustHave, 'Search')).toBe(false)
  })
})
