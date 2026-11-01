import { start } from '../../content/welcome'

interface ExampleIdeasProps {
  /** Called with the example's text when one is chosen. */
  onChoose: (idea: string) => void
}

/**
 * A row of example ideas. Choosing one fills the idea input, so a visitor
 * who is not sure what to type can see the kind of thing Archway expects.
 *
 * They are plain buttons, so they work with the keyboard as well as the mouse.
 */
export function ExampleIdeas({ onChoose }: ExampleIdeasProps) {
  return (
    <div className="flex flex-col items-center gap-12">
      <p className="text-caption font-strong text-stone">{start.examplesLabel}</p>
      <ul className="flex flex-wrap justify-center gap-8">
        {start.examples.map((example) => (
          <li key={example}>
            <button
              type="button"
              onClick={() => onChoose(example)}
              className="inline-flex min-h-44 items-center rounded-pill border border-ink/15 bg-white/45 px-16 py-8 text-left text-body-sm text-stone transition-colors duration-200 hover:border-ink/30 hover:bg-white hover:text-ink"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
