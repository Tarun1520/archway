import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { studioAgentsCopy } from '../../../content/studio'
import { AGENTS, bubbleText, type StreamLine, type TeamPicture } from '../../../lib/agentTeam'

/**
 * The agents' thoughts as a running stream under the robots: what each one is
 * thinking (in simple words) and what they say to each other, in the order it
 * happened. Every line of the run is kept: the list scrolls, and follows the
 * newest line (typed out at the bottom) unless you have scrolled up to read. Everything comes from what the agents really did
 * (lib/agentThoughts.ts and the run's team messages).
 */
export function AgentThoughts({ team }: { team: TeamPicture }) {
  const lines = team.stream
  const scroller = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLOListElement>(null)
  const following = useRef(true) // false only while the person has scrolled up to read older lines
  const byPerson = useRef(false) // true for a moment after the person's own wheel, touch, drag or key press
  const settle = useRef(0)

  // Following is judged only from scrolling the PERSON did. Our own jump to the
  // bottom also fires a scroll event, a moment later, by which time the list may
  // have grown again; judging that one would wrongly read as "scrolled up".
  const personScrolls = () => {
    byPerson.current = true
    window.clearTimeout(settle.current)
    settle.current = window.setTimeout(() => (byPerson.current = false), 300)
  }

  const pinToBottom = () => {
    const element = scroller.current
    if (element) element.scrollTop = element.scrollHeight
  }

  // Stay on the newest line: when a line is added AND while it types itself out
  // (the list grows as the letters appear), unless the person scrolled up to read.
  useEffect(() => {
    const list = content.current
    if (!list) return
    pinToBottom()
    const watcher = new ResizeObserver(() => {
      if (following.current) pinToBottom()
    })
    watcher.observe(list)
    return () => watcher.disconnect()
  }, [lines.length > 0])

  return (
    <section aria-label={studioAgentsCopy.thinking} className="px-4 pt-4 pb-8">
      <p className="mb-12 flex items-center gap-8 font-code text-label uppercase text-smoke">
        <span aria-hidden="true" className={`inline-block size-6 rounded-pill ${team.live ? 'live-dot bg-vermilion' : 'bg-slate'}`} />
        {studioAgentsCopy.thinking}
      </p>

      {lines.length === 0 ? (
        <p className="text-[14px] text-smoke">{studioAgentsCopy.waiting}</p>
      ) : (
        <div
          ref={scroller}
          onWheel={personScrolls}
          onTouchMove={personScrolls}
          onPointerDown={personScrolls}
          onKeyDown={personScrolls}
          onScroll={(event) => {
            if (!byPerson.current) return
            const e = event.currentTarget
            following.current = e.scrollHeight - e.scrollTop - e.clientHeight < 40 // back near the bottom: follow again
          }}
          // Fades out at the top edge, so older lines melt away instead of being cut off.
          style={{ maskImage: 'linear-gradient(to bottom, transparent 0, #000 18px)' }}
          // `relative` matters: the hidden screen-reader copies of each line are positioned
          // absolutely, and without a positioned parent they were laid out against the whole
          // page, stretching it by the height of the whole list (a blank page below the studio).
          className="relative max-h-[200px] overflow-y-auto pr-8 xl:max-h-[clamp(120px,calc(100dvh-640px),340px)]"
          tabIndex={0}
          aria-label={studioAgentsCopy.thinking}
        >
          <ol ref={content} className="flex flex-col gap-10 pt-12" aria-live="polite">
            {lines.map((line, index) => (
              <StreamRow key={line.id} line={line} age={lines.length - 1 - index} typing={index === lines.length - 1 && team.live} />
            ))}
          </ol>
        </div>
      )}

      {!team.live && team.started && <p className="mt-12 text-[13px] text-smoke">{studioAgentsCopy.allDone}</p>}
    </section>
  )
}

function nameOf(id: string): string {
  if (id === 'team') return studioAgentsCopy.everyone
  return AGENTS.find((a) => a.id === id)?.label ?? id
}

/** One line. `age` 0 is the newest; older lines are dimmer. */
function StreamRow({ line, age, typing }: { line: StreamLine; age: number; typing: boolean }) {
  const reduceMotion = useReducedMotion()
  const text = line.kind === 'thought' ? line.text : bubbleText(line.text, 120)
  const shown = useTypedText(text, typing && !reduceMotion)
  const who = line.kind === 'thought' ? nameOf(line.agent) : `${nameOf(line.from)} → ${nameOf(line.to)}`
  const isLead = line.kind === 'thought' ? line.agent === 'lead' : line.from === 'lead'

  return (
    <motion.li
      initial={reduceMotion || age > 2 ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: Math.max(0.6, 1 - age * 0.08), y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col gap-2"
    >
      <span className={`font-code text-[11px] uppercase tracking-[0.08em] ${isLead ? 'text-vermilion' : 'text-smoke'}`}>
        {who}
        {line.kind === 'message' && <span className="ml-6 text-slate">{studioAgentsCopy.says}</span>}
      </span>
      <span className={`text-[14px] leading-[1.45] ${line.kind === 'thought' ? 'text-chalk' : 'text-chalk/80 italic'}`}>
        {shown}
        {shown.length < text.length && <span aria-hidden="true" className="caret ml-1 inline-block h-[1em] w-[2px] translate-y-[2px] bg-vermilion" />}
      </span>
      {/* Screen readers get the whole line at once, not letter by letter. */}
      <span className="sr-only">{text}</span>
    </motion.li>
  )
}

/** Reveals `text` a few letters at a time, like someone typing; all at once when `animate` is false. */
function useTypedText(text: string, animate: boolean): string {
  const [count, setCount] = useState(animate ? 0 : text.length)
  useEffect(() => {
    if (!animate) {
      setCount(text.length)
      return
    }
    setCount(0)
    const perLetter = Math.max(12, Math.min(28, 1100 / text.length)) // long lines type faster, so none takes over ~1 s
    const timer = window.setInterval(() => {
      setCount((current) => {
        if (current >= text.length) {
          window.clearInterval(timer)
          return current
        }
        return current + 1
      })
    }, perLetter)
    return () => window.clearInterval(timer)
  }, [text, animate])
  return text.slice(0, count)
}
