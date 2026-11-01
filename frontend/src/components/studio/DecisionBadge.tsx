import type { DecisionEngine } from '../../lib/decisions'

const BASE = 'inline-flex h-24 shrink-0 items-center gap-6 rounded-pill border px-10 font-code text-[11px] tracking-[0.08em] uppercase'

/**
 * WHO made a decision, as a small badge.
 *
 *   LAYA   a cyan light: the open-source decision model answered. Always named for what answered, never "Jev".
 *   other engines and fixtures: a quiet outline with their own name.
 *   not asked: dashed, because nothing was decided by a model (nothing is guessed in its place).
 *
 * The tooltip says in one sentence what that engine is.
 */
export function DecisionBadge({ engine }: { engine: DecisionEngine }) {
  if (engine.id === 'laya') {
    return (
      <span title={engine.detail} className={`${BASE} border-[#7fe8ff]/55 bg-[#7fe8ff]/10 text-[#7fe8ff]`}>
        <span aria-hidden="true" className="laya-dot size-6 rounded-pill bg-[#7fe8ff]" />
        {engine.label}
      </span>
    )
  }
  return (
    <span title={engine.detail} className={`${BASE} ${engine.id === 'none' ? 'border-dashed border-slate text-smoke' : 'border-line text-chalk/80'}`}>
      {engine.label}
    </span>
  )
}

/** Plain code decided (the eligibility gate): the counterpart of the Laya badge. */
export function RulesBadge() {
  return (
    <span
      title="Decided by plain rules in code (license, archived, finished apps). No model, and it always has the last word."
      className={`${BASE} border-line text-smoke`}
    >
      <span aria-hidden="true" className="size-6 rounded-[1px] bg-smoke" />
      Rules
    </span>
  )
}
