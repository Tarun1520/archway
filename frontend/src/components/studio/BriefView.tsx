import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { studioCopy } from '../../content/studio'
import { useSuggestions } from '../../hooks/useSuggestions'
import type { BriefEdit, ProjectBrief } from '../../lib/api/types'
import {
  addAssumption,
  addMustHave,
  addNiceToHave,
  addStack,
  alreadyIn,
  draftFromBrief,
  editFromDraft,
  isDirty,
  newItem,
  resolveUnknown,
  setConstraint,
} from '../../lib/briefEdit'
import type { BriefDraft, DraftItem } from '../../lib/briefEdit'
import { StudioButton } from './StudioButton'
import { AlertIcon, CheckIcon } from '../ui/icons'
import { AiSuggestions } from './AiSuggestions'
import type { SuggestionRow } from './AiSuggestions'

interface BriefViewProps {
  brief: ProjectBrief
  runId: string | null
  /** True while the run is paused for the user to approve or edit this brief. */
  canDecide: boolean
  working: boolean
  onApprove: () => void
  /** Saves the draft as a new version and approves that version. */
  onSaveAndApprove: (edit: BriefEdit) => void
}

// --- Small building blocks ----------------------------------------------------

function Card({ title, hint, children, dashed = false }: { title: string; hint?: string; children: ReactNode; dashed?: boolean }) {
  return (
    // Assumptions use a DASHED border, so they look different in shape, not only in color.
    <section className={`rounded-card bg-obsidian p-16 ${dashed ? 'border border-dashed border-ivory/50' : ''}`}>
      <h3 className="text-caption font-strong tracking-wide text-ash uppercase">{title}</h3>
      {hint && <p className="mt-4 text-caption text-ash">{hint}</p>}
      <div className="mt-12">{children}</div>
    </section>
  )
}

/** An editor on the left and its AI suggestions beside it (stacked on a phone). */
function Block({ editor, suggestions }: { editor: ReactNode; suggestions?: ReactNode }) {
  if (!suggestions) return <>{editor}</>
  return (
    <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)] xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:gap-24">
      {editor}
      {suggestions}
    </div>
  )
}

/** The conflicts card, shown both while editing and while reading. */
function ConflictsCard({ brief }: { brief: ProjectBrief }) {
  const requirementText = (id: string) => [...brief.must_have, ...brief.nice_to_have].find((item) => item.id === id)?.text ?? id
  if (brief.conflicts.length === 0) return null
  return (
    <section role="alert" className="rounded-card border border-ivory bg-obsidian p-16">
      <h3 className="flex items-center gap-8 text-caption font-strong tracking-wide text-ivory uppercase">
        <AlertIcon size={16} />
        {studioCopy.briefConflicts} ({brief.conflicts.length})
      </h3>
      <p className="mt-4 text-caption text-ash">{studioCopy.briefConflictsHint}</p>
      <ul className="mt-12 flex flex-col gap-12">
        {brief.conflicts.map((conflict) => (
          <li key={conflict.description} className="text-body-sm text-ivory">
            <Label>{studioCopy.briefConflictLabel}</Label>
            {conflict.description}
            {conflict.requirement_ids.length > 0 && (
              <ul className="mt-6 ml-16 list-disc text-ash">
                {conflict.requirement_ids.map((id) => (
                  <li key={id}>
                    <span className="font-mono text-caption">{id}</span> {requirementText(id)}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** A value that may be unknown. Unknown is shown as "Not stated", never as blank. */
function Value({ value }: { value: string | null }) {
  return value ? <span className="text-ivory">{value}</span> : <span className="text-ash italic">{studioCopy.notStated}</span>
}

function Label({ children }: { children: ReactNode }) {
  return (
    <span className="mr-8 inline-flex h-20 shrink-0 items-center rounded-default border border-ivory/50 px-6 font-mono text-caption text-ivory">
      {children}
      {/* Unseen, but copied with the text: "Assumed: The model…", not "AssumedThe model…". */}
      <span className="sr-only">: </span>
    </span>
  )
}

const inputClasses = 'min-h-40 w-full rounded-default border border-mist/25 bg-transparent px-12 py-8 text-body-sm text-ivory'

/** An editable list of text rows with Add and Remove. */
function ItemEditor({ label, items, onChange }: { label: string; items: DraftItem[]; onChange: (items: DraftItem[]) => void }) {
  return (
    <div className="flex flex-col gap-8">
      {items.map((item, index) => (
        <div key={item.key} className="flex items-start gap-8">
          <input
            aria-label={`${label} ${index + 1}`}
            value={item.text}
            onChange={(event) => onChange(items.map((other) => (other.key === item.key ? { ...other, text: event.target.value } : other)))}
            className={inputClasses}
          />
          <button
            type="button"
            aria-label={`${studioCopy.removeItem} ${label} ${index + 1}`}
            onClick={() => onChange(items.filter((other) => other.key !== item.key))}
            className="mt-4 h-32 shrink-0 rounded-control px-12 text-caption text-ash hover:text-ivory"
          >
            {studioCopy.removeItem}
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...items, newItem()])}
        className="h-32 self-start rounded-control border border-mist/25 px-12 text-caption text-ivory hover:bg-ivory/10"
      >
        {studioCopy.addItem}
      </button>
    </div>
  )
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-4 text-caption text-ash">
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={studioCopy.notStated} className={inputClasses} />
    </label>
  )
}

/** One open question: the question itself, AI answers for it, and a box for your own answer. */
function UnknownRow({
  item,
  answers,
  state,
  onRetry,
  onQuestionChange,
  onRemove,
  onAnswer,
}: {
  item: DraftItem
  answers: { text: string; reason: string | null; add_as: 'must_have' | 'assumption'; standard: boolean }[]
  state: Parameters<typeof AiSuggestions>[0]['state']
  onRetry: () => void
  onQuestionChange: (text: string) => void
  onRemove: () => void
  onAnswer: (answer: string, addAs: 'must_have' | 'assumption') => void
}) {
  const [own, setOwn] = useState('')
  const rows: SuggestionRow[] = answers.map((answer) => ({
    id: `answer-${answer.text}`,
    text: answer.text,
    reason: answer.reason,
    standard: answer.standard,
    tag: answer.add_as === 'must_have' ? studioCopy.aiAddedToMustHave : studioCopy.aiAddedToAssumptions,
  }))

  return (
    <div className="flex flex-col gap-8 rounded-card border border-mist/15 p-12">
      <div className="flex items-start gap-8">
        <input
          aria-label={studioCopy.briefUnknowns}
          value={item.text}
          onChange={(event) => onQuestionChange(event.target.value)}
          className={inputClasses}
        />
        <button
          type="button"
          onClick={onRemove}
          className="mt-4 h-32 shrink-0 rounded-control px-12 text-caption text-ash hover:text-ivory"
        >
          {studioCopy.removeItem}
        </button>
      </div>

      <div className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)] xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] xl:gap-24">
        <div className="flex flex-col gap-8">
          <label className="flex flex-col gap-4 text-caption text-ash">
            {studioCopy.aiOwnIdea}
            <input
              value={own}
              onChange={(event) => setOwn(event.target.value)}
              placeholder={studioCopy.aiOwnAnswerLabel}
              maxLength={200}
              className={inputClasses}
            />
          </label>
          <button
            type="button"
            disabled={own.trim() === ''}
            onClick={() => {
              onAnswer(own.trim(), 'must_have')
              setOwn('')
            }}
            className="h-32 self-start rounded-control border border-mist/25 px-12 text-caption text-ivory hover:bg-ivory/10 disabled:opacity-50"
          >
            {studioCopy.aiOwnAnswerAdd}
          </button>
        </div>
        <AiSuggestions
          forBlock={item.text}
          state={state}
          onRetry={onRetry}
          rows={rows}
          quietSource
          emptyText={studioCopy.aiNothingMore}
          onAdd={(row) => {
            const answer = answers.find((candidate) => `answer-${candidate.text}` === row.id)
            if (answer) onAnswer(answer.text, answer.add_as)
          }}
        />
      </div>
    </div>
  )
}

// --- The brief ---------------------------------------------------------------

/**
 * The project brief: what Archway understood, laid out as cards.
 *
 * Three things are kept visibly apart, because mixing them up is how a brief
 * goes wrong:
 *   - what YOU said        (must have, constraints, "in your words")
 *   - what Archway ASSUMED (dashed cards, each labeled "Assumed")
 *   - what CONFLICTS       (labeled "Conflict", naming the requirements)
 *
 * Editing never changes a saved version. "Save as new version" sends the edit
 * to the backend, which creates version N+1, re-checks conflicts, and waits
 * for approval again. Approval always belongs to one exact version.
 */
export function BriefView({ brief, runId, canDecide, working, onApprove, onSaveAndApprove }: BriefViewProps) {
  // While the run waits for a decision the brief opens straight into an
  // editable DRAFT. (It is created once; a new version remounts this view.)
  const [draft, setDraft] = useState<BriefDraft | null>(() => (canDecide ? draftFromBrief(brief) : null))
  useEffect(() => {
    if (canDecide && draft === null) setDraft(draftFromBrief(brief))
    if (!canDecide && draft !== null) setDraft(null)
  }, [canDecide, draft, brief])

  const set = <K extends keyof BriefDraft>(key: K, value: BriefDraft[K]) =>
    setDraft((current) => (current ? { ...current, [key]: value } : current))
  const update = (change: (current: BriefDraft) => BriefDraft) => setDraft((current) => (current ? change(current) : current))

  // Ideas from the model, asked for once per brief version while drafting.
  const { state: suggestions, retry } = useSuggestions(runId, brief.version, canDecide && draft !== null)
  const ready = suggestions.status === 'ready' ? suggestions.data : null

  const header = (
    <header className="flex flex-wrap items-center gap-12">
      <h2 className="text-body-lg font-strong text-ivory">{studioCopy.briefHeading}</h2>
      <span className="font-mono text-caption text-ash">
        {studioCopy.briefVersion} {brief.version}
      </span>
      <span className="inline-flex items-center gap-6 text-caption text-ivory">
        {brief.confirmed ? <CheckIcon size={14} /> : null}
        {brief.confirmed ? studioCopy.briefConfirmed : studioCopy.briefUnconfirmed}
      </span>
      {draft && <Label>{studioCopy.draftBadge}</Label>}
    </header>
  )

  // --- Edit mode (the draft) -----------------------------------------------------
  if (draft) {
    const dirty = isDirty(draft, brief)
    const canSave = draft.problem.trim() !== '' && !working
    const edit = editFromDraft(draft)

    // Suggestions already added (or typed by the user) are not offered again.
    const mustHaveRows: SuggestionRow[] = (ready?.must_have ?? [])
      .filter((item) => !alreadyIn(draft.mustHave, item.text))
      .map((item) => ({ id: `must-${item.text}`, text: item.text, reason: item.reason }))

    const constraintLabel = { budget: 'Budget', privacy: 'Privacy', deployment: 'Deployment', stated: 'Other limit' } as const
    const constraintRows: SuggestionRow[] = (ready?.constraints ?? [])
      .filter((item) => !(item.field === 'stated' && alreadyIn(draft.stated, item.text)))
      .filter((item) => item.field === 'stated' || draft[item.field].trim() !== item.text)
      .map((item) => ({
        id: `constraint-${item.field}-${item.text}`,
        text: item.text,
        reason: item.reason,
        tag: constraintLabel[item.field],
        actionLabel: item.field !== 'stated' && draft[item.field].trim() !== '' ? studioCopy.aiReplace : studioCopy.aiAdd,
      }))

    const assumptionRows: SuggestionRow[] = (ready?.assumptions ?? [])
      .filter((item) => !alreadyIn(draft.assumptions, item.text))
      .map((item) => ({ id: `assume-${item.text}`, text: item.text, reason: item.reason }))

    const niceRows: SuggestionRow[] = (ready?.nice_to_have ?? [])
      .filter((item) => !alreadyIn(draft.niceToHave, item.text))
      .map((item) => ({ id: `nice-${item.text}`, text: item.text, reason: item.reason }))
    const stackRows: SuggestionRow[] = (ready?.stack ?? [])
      .filter((item) => !alreadyIn(draft.stack, item.text))
      .map((item) => ({ id: `stack-${item.text}`, text: item.text, reason: item.reason }))

    const addConstraint = (row: SuggestionRow) => {
      const item = ready?.constraints.find((candidate) => `constraint-${candidate.field}-${candidate.text}` === row.id)
      if (item) update((current) => setConstraint(current, item.field, item.text))
    }

    return (
      <form
        className="flex flex-col gap-12 p-20"
        onSubmit={(event) => {
          // Pressing Enter in a field must not save or approve anything.
          event.preventDefault()
        }}
      >
        {header}
        <p className="max-w-640 text-body-sm text-ash">{studioCopy.draftIntro}</p>

        <ConflictsCard brief={brief} />

        <Card title={studioCopy.briefProblem}>
          <textarea
            aria-label={studioCopy.briefProblem}
            value={draft.problem}
            onChange={(event) => set('problem', event.target.value)}
            rows={3}
            className={inputClasses}
          />
          <div className="mt-12">
            <TextField label={studioCopy.briefUsers} value={draft.users} onChange={(value) => set('users', value)} />
          </div>
        </Card>

        <Block
          editor={
            <Card title={studioCopy.briefMustHave}>
              <ItemEditor label={studioCopy.briefMustHave} items={draft.mustHave} onChange={(items) => set('mustHave', items)} />
            </Card>
          }
          suggestions={
            <AiSuggestions
              forBlock={studioCopy.briefMustHave}
              state={suggestions}
              onRetry={retry}
              rows={mustHaveRows}
              onAdd={(row) => update((current) => addMustHave(current, row.text))}
            />
          }
        />

        <Block
          editor={
            <Card title={studioCopy.briefConstraints}>
              <div className="grid gap-12 sm:grid-cols-3">
                <TextField label="Budget" value={draft.budget} onChange={(value) => set('budget', value)} />
                <TextField label="Privacy" value={draft.privacy} onChange={(value) => set('privacy', value)} />
                <TextField label="Deployment" value={draft.deployment} onChange={(value) => set('deployment', value)} />
              </div>
              <p className="mt-16 mb-8 text-caption text-ash">{studioCopy.briefStated}</p>
              <ItemEditor label={studioCopy.briefStated} items={draft.stated} onChange={(items) => set('stated', items)} />
            </Card>
          }
          suggestions={
            <AiSuggestions
              forBlock={studioCopy.briefConstraints}
              state={suggestions}
              onRetry={retry}
              rows={constraintRows}
              onAdd={addConstraint}
              quietSource
            />
          }
        />

        <Block
          editor={
            <Card title={studioCopy.briefAssumptions} hint={studioCopy.briefAssumptionsHint} dashed>
              <ItemEditor label={studioCopy.briefAssumptions} items={draft.assumptions} onChange={(items) => set('assumptions', items)} />
            </Card>
          }
          suggestions={
            <AiSuggestions
              forBlock={studioCopy.briefAssumptions}
              state={suggestions}
              onRetry={retry}
              rows={assumptionRows}
              onAdd={(row) => update((current) => addAssumption(current, row.text))}
              quietSource
            />
          }
        />

        {/* Each open question gets its own AI answers, plus a box for the user's own. */}
        <Card title={studioCopy.briefUnknowns} hint={studioCopy.briefUnknownsHint}>
          {draft.unknowns.length === 0 && <p className="text-body-sm text-ash italic">{studioCopy.aiNothingMore}</p>}
          <div className="flex flex-col gap-16">
            {draft.unknowns.map((item) => (
              <UnknownRow
                key={item.key}
                item={item}
                answers={ready?.unknowns.find((group) => group.unknown.trim().toLowerCase() === item.text.trim().toLowerCase())?.answers ?? []}
                state={suggestions}
                onRetry={retry}
                onQuestionChange={(text) =>
                  set('unknowns', draft.unknowns.map((other) => (other.key === item.key ? { ...other, text } : other)))
                }
                onRemove={() => set('unknowns', draft.unknowns.filter((other) => other.key !== item.key))}
                onAnswer={(answer, addAs) => update((current) => resolveUnknown(current, item.key, answer, addAs))}
              />
            ))}
          </div>
        </Card>

        <Block
          editor={
            <Card title={studioCopy.briefNiceToHave}>
              <ItemEditor label={studioCopy.briefNiceToHave} items={draft.niceToHave} onChange={(items) => set('niceToHave', items)} />
            </Card>
          }
          suggestions={
            <AiSuggestions
              forBlock={studioCopy.briefNiceToHave}
              state={suggestions}
              onRetry={retry}
              rows={niceRows}
              onAdd={(row) => update((current) => addNiceToHave(current, row.text))}
              quietSource
            />
          }
        />
        <Block
          editor={
            <Card title={studioCopy.briefStack}>
              <ItemEditor label={studioCopy.briefStack} items={draft.stack} onChange={(items) => set('stack', items)} />
            </Card>
          }
          suggestions={
            <AiSuggestions
              forBlock={studioCopy.briefStack}
              state={suggestions}
              onRetry={retry}
              rows={stackRows}
              onAdd={(row) => update((current) => addStack(current, row.text))}
              quietSource
            />
          }
        />

        {dirty && <p className="text-caption text-ash">{studioCopy.briefUnsaved}</p>}
        <div className="flex flex-wrap gap-12">
          {dirty ? (
            <StudioButton disabled={!canSave} onClick={() => onSaveAndApprove(edit)}>
              {studioCopy.briefSaveAndApprove}
            </StudioButton>
          ) : (
            <StudioButton disabled={working} onClick={onApprove}>
              {studioCopy.briefApprove}
            </StudioButton>
          )}
          {dirty && (
            <StudioButton variant="outline" disabled={working} onClick={() => setDraft(draftFromBrief(brief))}>
              {studioCopy.briefRevert}
            </StudioButton>
          )}
        </div>
      </form>
    )
  }

  // --- Read mode ---------------------------------------------------------------
  return (
    <div className="flex flex-col gap-12 p-20">
      {header}

      <ConflictsCard brief={brief} />

      <Card title={studioCopy.briefProblem}>
        <p className="text-body text-ivory">{brief.problem}</p>
        <p className="mt-8 text-body-sm">
          <span className="text-ash">{studioCopy.briefUsers}: </span>
          <Value value={brief.users} />
        </p>
      </Card>

      <div className="grid gap-12 lg:grid-cols-2">
        <Card title={`${studioCopy.briefMustHave} (${brief.must_have.length})`}>
          <ul className="flex flex-col gap-8">
            {brief.must_have.length === 0 && <li className="text-body-sm text-ash italic">{studioCopy.notStated}</li>}
            {brief.must_have.map((item) => (
              <li key={item.id} className="flex gap-8 text-body-sm text-ivory">
                {item.text}
              </li>
            ))}
          </ul>
        </Card>

        <Card title={studioCopy.briefConstraints}>
          <dl className="grid grid-cols-[88px_1fr] gap-x-12 gap-y-6 text-body-sm">
            <dt className="text-ash">Budget</dt>
            <dd><Value value={brief.constraints.budget} /></dd>
            <dt className="text-ash">Privacy</dt>
            <dd><Value value={brief.constraints.privacy} /></dd>
            <dt className="text-ash">Deployment</dt>
            <dd><Value value={brief.constraints.deployment} /></dd>
          </dl>
          {brief.constraints.stated.length > 0 && (
            <>
              <p className="mt-12 text-caption text-ash">
                {studioCopy.briefStated}. {studioCopy.briefStatedHint}
              </p>
              <ul className="mt-6 flex flex-col gap-6">
                {brief.constraints.stated.map((sentence) => (
                  <li key={sentence} className="border-l-2 border-ivory/60 pl-12 text-body-sm text-ivory">
                    “{sentence}”
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>

      {brief.assumptions.length > 0 && (
        <Card title={`${studioCopy.briefAssumptions} (${brief.assumptions.length})`} hint={studioCopy.briefAssumptionsHint} dashed>
          <ul className="flex flex-col gap-10">
            {brief.assumptions.map((item) => (
              <li key={item.id} className="text-body-sm text-ivory">
                <Label>{studioCopy.briefAssumptionLabel}</Label>
                {item.text}
                {item.reason && <span className="block pl-2 text-caption text-ash">{item.reason}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-12 lg:grid-cols-2">
        {brief.nice_to_have.length > 0 && (
          <Card title={studioCopy.briefNiceToHave}>
            <ul className="flex flex-col gap-6 text-body-sm text-ivory">
              {brief.nice_to_have.map((item) => (
                <li key={item.id}>{item.text}</li>
              ))}
            </ul>
          </Card>
        )}
        {brief.unknowns.length > 0 && (
          <Card title={studioCopy.briefUnknowns}>
            <ul className="ml-16 flex list-disc flex-col gap-6 text-body-sm text-ivory">
              {brief.unknowns.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Card>
        )}
        {brief.stack_preferences.length > 0 && (
          <Card title={studioCopy.briefStack}>
            <p className="text-body-sm text-ivory">{brief.stack_preferences.join(', ')}</p>
          </Card>
        )}
      </div>

    </div>
  )
}
