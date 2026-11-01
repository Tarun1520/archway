import { motion, useInView } from 'motion/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { studioUi } from '../../../content/studio'
import type { PlanSnapshot } from '../../../lib/api/types'
import { BAND_HEADER, NODE_HEIGHT, layoutPlanFlow, type FlowNode } from '../../../lib/planFlow'
import { stageTitle } from '../../../lib/plan'
import { usePrefersReducedMotion } from '../../../hooks/usePrefersReducedMotion'

const copy = studioUi.plan.flow

/** Seconds between one band appearing and the next: the chart draws itself in build order. */
const STEP = 0.5
const SPIKE = '#7fe8ff'

/**
 * The build flow chart: the whole plan as one picture, read top to bottom in build order.
 *
 *   bands     one per prompt (01 Scaffold at the top, then 02 ...), with its tasks side by side; the last band holds
 *             the requirements the work delivers
 *   arrows    from each task down to the tasks that need it, and from a task to the requirements it delivers
 *
 * It always fits the width it has (the layout is worked out for that width: lib/planFlow.ts), so nobody has to scroll
 * sideways; on a phone the tasks of a band simply stack.
 *
 * When it scrolls into view it draws itself: each band fades in after the one above, and the arrows into it trace
 * themselves from their source, so the order of the work is visible. Afterwards a slow pulse runs along the arrows.
 * A spike (a small experiment that settles an uncertain part first) is drawn in cyan; prompts marked as done are
 * ticked. Every task is a button: choosing one shows its details below the chart. With reduced motion the chart is
 * simply shown, complete and still.
 */
export function PlanFlow({ plan }: { plan: PlanSnapshot }) {
  const frame = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const element = frame.current
    if (!element) return
    const measure = () => setWidth(Math.floor(element.clientWidth - 32)) // the frame's padding, 16px a side
    measure()
    const watcher = new ResizeObserver(measure)
    watcher.observe(element)
    return () => watcher.disconnect()
  }, [])
  const layout = useMemo(() => layoutPlanFlow(plan, Math.max(200, width)), [plan, width])
  const seen = useInView(frame, { once: true, amount: 0.1 })
  const still = usePrefersReducedMotion()
  const [round, setRound] = useState(0) // bumping it replays the drawing
  const [selected, setSelected] = useState<string | null>(null)
  const done = new Set(plan.completed)
  const active = (seen || still) && width > 0
  const finish = layout.bands.length * STEP + 0.9 // when the last arrows have finished drawing

  const doneBand = (path: string | null) => path !== null && done.has(path)
  const chosen = layout.nodes.find((node) => node.id === selected && node.kind === 'task')
  const highlighted = new Set<string>(
    chosen ? [chosen.id, ...layout.arrows.filter((a) => a.from === chosen.id || a.to === chosen.id).flatMap((a) => [a.from, a.to])] : [],
  )

  if (layout.nodes.length === 0) return null

  return (
    <section className="flex flex-col gap-16">
      <div className="flex max-w-3xl flex-wrap items-end justify-between gap-12">
        <div>
          <h3 className="text-h3 font-bold text-chalk">{copy.title}</h3>
          <p className="mt-8 text-[16px] leading-[1.6] text-smoke">{copy.lead}</p>
        </div>
        {!still && (
          <button
            type="button"
            onClick={() => setRound((value) => value + 1)}
            className="min-h-44 px-4 font-code text-label uppercase text-smoke underline decoration-line decoration-2 underline-offset-[6px] hover:text-chalk focus-visible:outline-2 focus-visible:outline-vermilion"
          >
            {copy.replay}
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-20 gap-y-8 font-code text-[12px] text-smoke" aria-hidden="true">
        <span className="inline-flex items-center gap-8"><span className="h-px w-24 bg-chalk/60" />{copy.legendNeeds}</span>
        <span className="inline-flex items-center gap-8"><span className="h-px w-24 border-t border-dashed border-vermilion" />{copy.legendDelivers}</span>
        <span className="inline-flex items-center gap-8"><span className="size-10 rounded-[3px] border" style={{ borderColor: SPIKE }} />{copy.legendSpike}</span>
      </div>

      <div ref={frame} className="rounded-card border border-line bg-carbon/50 p-16" role="group" aria-label={copy.title}>
        <div key={round} className="relative mx-auto" style={{ width: layout.width, height: layout.height }}>
          {/* Arrows, under the nodes */}
          <svg width={layout.width} height={layout.height} className="absolute inset-0 overflow-visible" aria-hidden="true">
            <defs>
              <marker id="flow-head" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 8 4 L 0 8 z" fill="currentColor" />
              </marker>
            </defs>
            {layout.arrows.map((arrow) => {
              const lit = highlighted.size === 0 || (highlighted.has(arrow.from) && highlighted.has(arrow.to))
              const delivers = arrow.kind === 'delivers'
              const colour = delivers ? 'var(--color-vermilion)' : 'var(--color-chalk)'
              const delay = arrow.band * STEP + 0.15
              return (
                <g key={arrow.id} style={{ color: colour, opacity: lit ? 1 : 0.15, transition: 'opacity 200ms' }}>
                  <motion.path
                    d={arrow.path}
                    fill="none"
                    stroke="currentColor"
                    strokeOpacity={delivers ? 0.7 : 0.45}
                    strokeWidth={1.5}
                    strokeDasharray={delivers ? '5 5' : undefined}
                    markerEnd="url(#flow-head)"
                    initial={still ? false : { pathLength: 0, opacity: 0 }}
                    animate={active ? { pathLength: 1, opacity: 1 } : undefined}
                    transition={{ pathLength: { delay, duration: 0.7, ease: 'easeInOut' }, opacity: { delay, duration: 0.1 } }}
                  />
                  {/* The slow flow along the arrow, once everything is drawn */}
                  {!still && active && (
                    <path
                      d={arrow.path}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      className="plan-flow-pulse"
                      style={{ animationDelay: `${finish + (arrow.band % 3) * 0.4}s` }}
                    />
                  )}
                </g>
              )
            })}
          </svg>

          {/* Band titles: which prompt each band is */}
          {layout.bands.map((band) => (
            <motion.div
              key={band.index}
              className="absolute left-0 flex items-baseline gap-10 border-t border-line/70 pt-8"
              style={{ top: band.y, width: layout.width, height: BAND_HEADER - 20 }}
              initial={still ? false : { opacity: 0 }}
              animate={active ? { opacity: 1 } : undefined}
              transition={{ delay: band.index * STEP, duration: 0.4 }}
            >
              <span className="font-code text-[11px] uppercase tracking-[0.08em] text-smoke">{band.path ? copy.prompt : copy.result}</span>
              <span className={`text-[15px] font-semibold ${doneBand(band.path) ? 'text-chalk/60' : 'text-chalk'}`}>{band.title}</span>
              {doneBand(band.path) && <span className="font-code text-[11px] uppercase text-chalk/70">✓ {studioUi.plan.done}</span>}
            </motion.div>
          ))}

          {/* Nodes */}
          {layout.nodes.map((node) => (
            <motion.div
              key={node.id}
              className="absolute"
              style={{ left: node.x, top: node.y, width: node.width, height: NODE_HEIGHT }}
              initial={still ? false : { opacity: 0, y: 14, scale: 0.97 }}
              animate={active ? { opacity: highlighted.size === 0 || highlighted.has(node.id) ? 1 : 0.35, y: 0, scale: 1 } : undefined}
              transition={{ delay: node.band * STEP + (node.row * 3 + node.slot) * 0.06, duration: 0.45, ease: 'easeOut' }}
            >
              {node.kind === 'task' ? (
                <TaskNode node={node} selected={selected === node.id} done={done.has(pathOf(plan, node.id) ?? '')}
                  onSelect={() => setSelected((now) => (now === node.id ? null : node.id))} />
              ) : (
                <RequirementNode node={node} />
              )}
            </motion.div>
          ))}
        </div>
      </div>

      {chosen?.task && (
        <div className="flex max-w-3xl flex-col gap-10 rounded-card border border-line bg-carbon/80 p-20" aria-live="polite">
          <p className="font-code text-label uppercase text-smoke">
            {chosen.task.id} · {stageTitle(chosen.task.stage)}
            {chosen.task.kind === 'spike' ? ` · ${studioUi.plan.spike}` : ''}
          </p>
          <p className="text-[18px] font-semibold text-chalk">{chosen.task.title}</p>
          <p className="text-[15px] leading-[1.6] text-chalk/90">{chosen.task.scope}</p>
          <Detail label={copy.needs} items={chosen.task.prerequisites} empty={studioUi.plan.nothingFirst} />
          <Detail label={copy.parts} items={chosen.task.components} empty={copy.noParts} />
          <Detail label={copy.doneWhen} items={chosen.task.acceptance_criteria} empty="—" />
          <Detail label={copy.checks} items={chosen.task.validation_steps} empty="—" />
          {chosen.task.risks.length > 0 && <Detail label={copy.risks} items={chosen.task.risks} empty="" />}
        </div>
      )}
    </section>
  )
}

function pathOf(plan: PlanSnapshot, taskId: string): string | undefined {
  return plan.files.find((file) => file.kind === 'prompt' && file.task_ids.includes(taskId))?.path
}

function TaskNode({ node, selected, done, onSelect }: { node: FlowNode; selected: boolean; done: boolean; onSelect: () => void }) {
  const task = node.task!
  const spike = task.kind === 'spike'
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex h-full w-full flex-col gap-4 rounded-card border bg-soot p-12 text-left transition-colors hover:bg-carbon focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion ${
        selected ? 'border-chalk' : spike ? '' : 'border-line'
      }`}
      style={spike && !selected ? { borderColor: `${SPIKE}99` } : undefined}
    >
      <span className="flex items-center justify-between gap-8 font-code text-[11px] uppercase tracking-[0.08em]">
        <span className={done ? 'text-chalk/50' : 'text-smoke'}>
          {task.id}
          <span className="sr-only">: </span>
        </span>
        {spike && <span style={{ color: SPIKE }}>{studioUi.plan.spike}</span>}
        {done && <span className="text-chalk/70">✓</span>}
      </span>
      <span className={`line-clamp-2 text-[14px] font-medium leading-[1.35] ${done ? 'text-chalk/55' : 'text-chalk'}`}>{task.title}</span>
      <span className="mt-auto line-clamp-1 font-code text-[11px] text-smoke">
        {task.components.length > 0 ? task.components.join(' · ') : task.requirement_ids.join(' · ') || ' '}
      </span>
    </button>
  )
}

function RequirementNode({ node }: { node: FlowNode }) {
  return (
    <div
      className={`flex h-full w-full flex-col gap-4 rounded-card border p-12 ${node.delivered ? 'border-vermilion/60 bg-vermilion/5' : 'border-dashed border-slate bg-transparent'}`}
    >
      <span className="font-code text-[11px] uppercase tracking-[0.08em] text-smoke">
        {node.id}
        <span className="sr-only">: </span>
        {!node.delivered && ` · ${copy.notDelivered}`}
      </span>
      <span className="line-clamp-3 text-[13px] leading-[1.4] text-chalk/90">{node.text}</span>
    </div>
  )
}

function Detail({ label, items, empty }: { label: string; items: string[]; empty: string }) {
  return (
    <div className="flex flex-col gap-4">
      <span className="font-code text-[12px] uppercase text-smoke">{label}</span>
      {items.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item} className="text-[14px] leading-[1.5] text-chalk/85">{item}</li>
          ))}
        </ul>
      ) : (
        <span className="text-[14px] text-smoke">{empty}</span>
      )}
    </div>
  )
}
