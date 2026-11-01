import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { start } from '../../content/welcome'
import { IDEA_INPUT_ID } from '../../lib/focusIdeaInput'
import { MAX_IDEA_LENGTH, startProject } from '../../lib/startProject'
import type { StartProjectResult } from '../../lib/startProject'
import { useGlow } from '../../hooks/useGlow'
import { useGoToWorkspace } from '../../hooks/useGoToWorkspace'
import { BrandMark } from '../ui/BrandMark'
import { Button } from '../ui/Button'
import { WorkspaceLink } from './WorkspaceLink'
import { AlertIcon, CheckIcon } from '../ui/icons'

/** The message shown under the form after a submit. `null` means nothing to say yet. */
interface Feedback {
  kind: 'saved' | 'problem'
  text: string
}

/** Turns the result of `startProject` into words for the person. */
function describeResult(result: StartProjectResult): Feedback {
  if (result.ok) {
    return {
      kind: 'saved',
      // Shown for a moment while the studio opens. The studio turns the idea
      // into a saved project; no research starts yet.
      text: 'Opening the studio…',
    }
  }

  const problems: Record<typeof result.reason, string> = {
    empty: 'Describe your idea first. One sentence is enough.',
    too_long: `Keep it under ${MAX_IDEA_LENGTH} characters. You can add detail in the brief later.`,
    storage_unavailable: 'This browser blocked saving the idea, so nothing was kept.',
  }
  return { kind: 'problem', text: problems[result.reason] }
}

interface IdeaFormProps {
  /** The text in the input. It is kept by the parent, so other controls (the example buttons) can fill it in. */
  idea: string
  onIdeaChange: (idea: string) => void
}

/**
 * The idea form: a long text input in a glowing pill, with the glowing
 * "Start a project" button beside it.
 *
 * The form does not decide what "starting a project" means. It hands the text
 * to `startProject` and shows whatever comes back.
 */
export function IdeaForm({ idea, onIdeaChange }: IdeaFormProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  // Makes the input's pill glow toward the pointer.
  const pillRef = useGlow<HTMLDivElement>()
  const goToWorkspace = useGoToWorkspace()

  // A message is about the text that was submitted. Once the text changes,
  // the message no longer applies, so clear it.
  useEffect(() => {
    setFeedback(null)
  }, [idea])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault() // stop the browser from reloading the page
    const result = startProject(idea)
    setFeedback(describeResult(result))
    // The idea is now kept in this tab. Go to the studio (through the space
    // transition), which picks it up and saves it as a project (see
    // lib/pendingIdea.ts and hooks/useProjects.ts).
    if (result.ok) goToWorkspace()
  }

  const hasProblem = feedback?.kind === 'problem'

  // Status is shown with an icon and words, never with color alone.
  let feedbackIcon: ReactNode = null
  if (feedback) {
    feedbackIcon = feedback.kind === 'saved' ? <CheckIcon size={16} /> : <AlertIcon size={16} />
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="w-full max-w-880">
      <div className="flex flex-col items-stretch justify-center gap-16 sm:flex-row sm:items-center">
        {/*
          The input sits inside a glow pill (see `glow-pill` in
          styles/index.css). The focus ring is drawn around the whole pill
          instead of the bare input inside it: `has-[input:focus-visible]`
          means "when the input in here has keyboard focus".
        */}
        <div
          ref={pillRef}
          className="glow-pill flex h-60 items-center rounded-control px-24 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-4 has-[input:focus-visible]:outline-cobalt sm:min-w-0 sm:flex-1"
        >
          <label htmlFor={IDEA_INPUT_ID} className="sr-only">
            {start.inputLabel}
          </label>
          <input
            id={IDEA_INPUT_ID}
            name="idea"
            type="text"
            value={idea}
            onChange={(event) => onIdeaChange(event.target.value)}
            placeholder={start.inputLabel}
            autoComplete="off"
            aria-invalid={hasProblem}
            aria-describedby="idea-feedback"
            className="h-full w-full min-w-0 bg-transparent text-body text-ink placeholder:text-stone focus-visible:outline-none sm:text-body-lg"
          />
        </div>

        <Button type="submit" size="lg" className="shrink-0">
          <BrandMark size={20} />
          {start.submitLabel}
        </Button>
      </div>

      <div className="mt-16 flex justify-center">
        <WorkspaceLink />
      </div>

      {/* `role="status"` makes screen readers announce the message when it appears. */}
      <p id="idea-feedback" role="status" className="mt-12 flex min-h-24 items-start justify-center">
        {feedback && (
          <span className="inline-flex items-start gap-8 text-body-sm text-ink">
            <span className="mt-2 shrink-0">{feedbackIcon}</span>
            <span>{feedback.text}</span>
          </span>
        )}
      </p>
    </form>
  )
}
