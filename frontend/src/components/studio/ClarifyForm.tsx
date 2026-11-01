import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { studioCopy } from '../../content/studio'
import type { ClarifyQuestion, Topic } from '../../lib/api/types'
import { StudioButton } from './StudioButton'

interface ClarifyFormProps {
  questions: ClarifyQuestion[]
  /** False when the only question is "what would you like to build?": there is nothing to assume yet. */
  allowContinue: boolean
  working: boolean
  /** Sends the answers. With `continueWithAssumptions`, unanswered topics become assumptions. */
  onAnswer: (answers: Partial<Record<Topic, string>>, continueWithAssumptions: boolean) => void
  /** Answers ARCHY has heard so far (he types them in as they are spoken). */
  voiceAnswers?: Record<string, string>
  /** The question ARCHY is asking right now: its box is marked, and typing waits for his listening. */
  voiceTopic?: string | null
}

/**
 * The questions Archway asks before confirming a brief.
 *
 * There are two ways forward:
 *   "Send answers"               every question answered
 *   "Continue with assumptions"  skip the rest; each skipped topic becomes a
 *                                visible assumption in the brief
 * The second is offered for the architecture questions. It is not offered for
 * "what would you like to build?": a project that has not been described
 * cannot have assumptions made about it.
 */
export function ClarifyForm({ questions, allowContinue, working, onAnswer, voiceAnswers, voiceTopic = null }: ClarifyFormProps) {
  const [answers, setAnswers] = useState<Partial<Record<Topic, string>>>({})

  // What ARCHY hears is typed into the boxes (a skipped question arrives as an empty string and clears its box).
  useEffect(() => {
    if (voiceAnswers) setAnswers((current) => ({ ...current, ...(voiceAnswers as Partial<Record<Topic, string>>) }))
  }, [voiceAnswers])
  const [needAll, setNeedAll] = useState(false)

  const allAnswered = questions.every((question) => (answers[question.topic] ?? '').trim() !== '')
  const askingForIdea = questions.some((question) => question.topic === 'idea')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!allAnswered) {
      setNeedAll(true)
      return
    }
    onAnswer(answers, false)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-16 p-20">
      <div>
        <h2 className="text-body-lg font-strong text-ivory">
          {askingForIdea ? studioCopy.ideaHeading : studioCopy.clarifyHeading}
        </h2>
        <p className="mt-4 max-w-640 text-body-sm text-ash">
          {askingForIdea ? studioCopy.ideaIntro : studioCopy.clarifyIntro}
        </p>
      </div>

      {questions.map((question) => (
        <div key={question.topic} className="flex max-w-640 flex-col gap-8">
          <label htmlFor={`clarify-${question.topic}`} className="text-body text-ivory">
            {question.question}
          </label>
          {question.why && (
            <p className="text-caption text-ash">
              {studioCopy.clarifyWhy} {question.why}
            </p>
          )}
          {question.topic === 'idea' ? (
            <textarea
              id="clarify-idea"
              value={answers.idea ?? ''}
              onChange={(event) => setAnswers((current) => ({ ...current, idea: event.target.value }))}
              maxLength={2000}
              rows={4}
              readOnly={voiceTopic === 'idea'}
              className={`rounded-card border bg-transparent px-20 py-12 text-body text-ivory transition-colors ${voiceTopic === 'idea' ? 'border-[#7fe8ff]/60' : 'border-mist/25'}`}
            />
          ) : (
            <input
              id={`clarify-${question.topic}`}
              value={answers[question.topic] ?? ''}
              onChange={(event) => setAnswers((current) => ({ ...current, [question.topic]: event.target.value }))}
              maxLength={500}
              autoComplete="off"
              readOnly={voiceTopic === question.topic}
              className={`h-44 rounded-control border bg-transparent px-20 text-body text-ivory transition-colors ${voiceTopic === question.topic ? 'border-[#7fe8ff]/60' : 'border-mist/25'}`}
            />
          )}
        </div>
      ))}

      {needAll && !allAnswered && (
        <p role="alert" className="text-body-sm text-ivory">
          {askingForIdea ? studioCopy.ideaHeading : studioCopy.clarifyNeedAll}
        </p>
      )}

      <div className="flex flex-wrap gap-12">
        <StudioButton type="submit" disabled={working}>
          {askingForIdea ? studioCopy.ideaSubmit : studioCopy.clarifySubmit}
        </StudioButton>
        {allowContinue && (
          <StudioButton variant="outline" disabled={working} onClick={() => onAnswer(answers, true)}>
            {studioCopy.clarifyContinue}
          </StudioButton>
        )}
      </div>
    </form>
  )
}
