/**
 * WHERE something was found, as a small badge: the same quiet outline as the
 * decision badges (DecisionBadge.tsx), with a grey dot. Used in the shortlist's
 * "where the agents looked" panel.
 */
export function SourceBadge({ name, detail }: { name: string; detail?: string }) {
  return (
    <span
      title={detail}
      className="inline-flex h-24 shrink-0 items-center gap-6 rounded-pill border border-line px-10 font-code text-[11px] tracking-[0.08em] text-chalk/80 uppercase"
    >
      <span aria-hidden="true" className="size-6 rounded-pill bg-slate" />
      {name}
    </span>
  )
}
