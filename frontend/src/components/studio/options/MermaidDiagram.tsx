import { useEffect, useId, useState } from 'react'
import { studioUi } from '../../../content/studio'
import { flowFromSource, quoteLabels } from '../../../lib/mermaidLabels'

/**
 * Draws a model-written Mermaid diagram, safely.
 *
 * Labels are put in quotes before drawing (lib/mermaidLabels.ts), because names like `@scope/package` are not
 * readable to Mermaid as bare text.
 *
 * Three layers keep it safe: the backend only lets a plain flowchart through (no HTML, links or click handlers:
 * backend/app/options/mermaid_safe.py); Mermaid is told to run in its "strict" security mode, which sanitises
 * the labels and turns clicking off; and if drawing fails for any reason the source is shown as plain text.
 *
 * The library is large, so it loads only when a diagram is first drawn (a dynamic import), never with the page.
 */
export function MermaidDiagram({ source, label }: { source: string; label: string }) {
  const id = `diagram-${useId().replace(/:/g, '')}`
  const [svg, setSvg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setSvg(null)
    setFailed(false)
    void (async () => {
      try {
        const { default: mermaid } = await import('mermaid')
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'dark',
          flowchart: { htmlLabels: false, useMaxWidth: true },
          fontFamily: 'inherit',
        })
        const drawn = await mermaid.render(id, quoteLabels(source)) // labels are quoted first: package names and paths break bare labels
        if (!cancelled) setSvg(drawn.svg)
      } catch {
        if (!cancelled) setFailed(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [source, id])

  if (failed) {
    // Still shown: the flow as a list, read from the arrows, and the source underneath.
    const steps = flowFromSource(quoteLabels(source))
    return (
      <div className="flex flex-col gap-12">
        <p className="text-[14px] text-smoke">{studioUi.options.diagramFailed}</p>
        {steps.length > 0 && (
          <ol className="flex flex-col gap-4 rounded-default border border-line bg-void/50 p-16">
            {steps.map((step, index) => (
              <li key={index} className="flex flex-wrap items-baseline gap-x-10 text-[15px] text-chalk/90">
                <span>{step.from}</span>
                <span aria-hidden="true" className="text-smoke">{step.label ? `— ${step.label} →` : '→'}</span>
                <span>{step.to}</span>
              </li>
            ))}
          </ol>
        )}
        <details>
          <summary className="cursor-pointer font-code text-label uppercase text-smoke">Source</summary>
          <pre className="mt-8 overflow-x-auto rounded-default border border-line bg-void/60 p-12 font-code text-[12px] text-chalk/80">{source}</pre>
        </details>
      </div>
    )
  }
  if (svg === null) return <p className="py-16 font-code text-label uppercase text-smoke">…</p>
  return (
    <div
      role="img"
      aria-label={label}
      className="overflow-x-auto rounded-default border border-line bg-void/50 p-16 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      // The markup comes from Mermaid's own renderer in strict mode, from a source the backend already restricted.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
