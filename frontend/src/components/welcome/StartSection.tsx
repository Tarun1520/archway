import { useState } from 'react'
import { start } from '../../content/welcome'
import { IDEA_INPUT_ID, START_SECTION_ID } from '../../lib/focusIdeaInput'
import { Reveal } from '../ui/Reveal'
import { Tag } from '../ui/Tag'
import { ExampleIdeas } from './ExampleIdeas'
import { IdeaForm } from './IdeaForm'

/**
 * The second screen: where a visitor actually starts.
 *
 * In the hero's video this is what the laptop is showing. As the camera
 * reaches the laptop, this screen fills the window and becomes the page
 * (ScreenHandoff.tsx does that). It is one full window tall for that reason:
 * what was on the laptop must be exactly what fills the window.
 *
 * Its background is the morning sky from the hero's picture, so stepping
 * "inside" the laptop feels like stepping into the same morning.
 *
 * It keeps the idea text itself (`useState`) because two different parts
 * need it: the form shows and submits it, and the example buttons fill it in.
 */
export function StartSection() {
  const [idea, setIdea] = useState('')

  const useExample = (example: string) => {
    setIdea(example)
    // Put the cursor in the input, so the example can be edited or sent at once.
    document.getElementById(IDEA_INPUT_ID)?.focus({ preventScroll: true })
  }

  return (
    <section
      id={START_SECTION_ID}
      data-fills-window // links to this screen land exactly at its top (see lib/inPageLinks.ts)
      className="bg-morning-sky relative flex min-h-svh flex-col items-center justify-center overflow-hidden px-20 pt-96 pb-56 text-center md:px-32"
    >
      {/* A large, faint arch behind the content: the Archway mark, as a doorway around the form. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMax meet"
        className="pointer-events-none absolute inset-x-0 bottom-0 mx-auto h-[92%] w-full max-w-page text-forest"
      >
        <path d="M14 100V44a36 36 0 0 1 72 0v56" fill="none" stroke="currentColor" strokeOpacity="0.1" strokeWidth="0.25" />
        <path d="M22 100V46a28 28 0 0 1 56 0v54" fill="none" stroke="currentColor" strokeOpacity="0.06" strokeWidth="0.25" />
      </svg>

      <div className="relative flex w-full max-w-960 flex-col items-center">
        <Reveal>
          <Tag tone="morning">{start.tag}</Tag>
          <h2 className="mt-20 text-display-fluid text-ink">{start.headline}</h2>
        </Reveal>

        <Reveal delay={0.08} className="max-w-760">
          <p className="mt-16 text-lead-fluid font-book text-stone md:mt-20">{start.summary}</p>
        </Reveal>

        <Reveal delay={0.16} className="mt-32 flex w-full justify-center md:mt-40">
          <IdeaForm idea={idea} onIdeaChange={setIdea} />
        </Reveal>

        <Reveal delay={0.24} className="mt-12">
          <ExampleIdeas onChoose={useExample} />
        </Reveal>
      </div>
    </section>
  )
}
