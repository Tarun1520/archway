import { studioUi } from '../../../content/studio'
import type { ArchitectureOption, Rating } from '../../../lib/api/types'
import { DIMENSION_LABEL, DIMENSION_ORDER, RATING_LABEL, mix } from '../../../lib/options'

const RATING_STYLE: Record<Rating, string> = {
  good: 'bg-chalk text-void',
  mixed: 'border border-line text-chalk/85',
  poor: 'border border-vermilion text-vermilion',
  unknown: 'border border-dashed border-slate text-smoke',
}

/**
 * The options side by side on the eight comparison dimensions. "Favourable" is always the good end of a row
 * (simple, light, private, cheap, well supported), so a column of white chips reads as "strong". The notes are
 * qualitative: no invented hours or savings.
 */
export function ComparisonTable({ options, selectedId, onPick }: { options: ArchitectureOption[]; selectedId: string | null; onPick: (id: string) => void }) {
  return (
    <section aria-label={studioUi.options.compare} className="flex flex-col gap-16">
      <p className="font-code text-label uppercase text-smoke">{studioUi.options.compare}</p>
      <div className="overflow-x-auto rounded-card border border-line">
        <table style={{ minWidth: 160 + options.length * 240 }} className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line align-bottom">
              <th scope="col" className="w-[160px] p-16" />
              {options.map((option) => (
                <th key={option.id} scope="col" className={`p-16 align-top ${option.id === selectedId ? 'bg-soot/50' : ''}`}>
                  <button type="button" onClick={() => onPick(option.id)} className="text-left focus-visible:outline-2 focus-visible:outline-vermilion">
                    <span className="block font-code text-label uppercase text-smoke">
                      {option.id} · v{option.version}
                    </span>
                    <span className="mt-4 block text-[17px] font-semibold text-chalk">{option.name}</span>
                    {option.trade_off && <span className="mt-6 block text-[13px] leading-[1.5] font-normal text-smoke">{option.trade_off}</span>}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-line">
              <th scope="row" className="p-16 font-code text-label font-normal uppercase text-smoke">
                Reuse / build
              </th>
              {options.map((option) => {
                const counts = mix(option)
                return (
                  <td key={option.id} className={`p-16 font-code text-[14px] text-chalk ${option.id === selectedId ? 'bg-soot/50' : ''}`}>
                    {counts.reuse} reused · {counts.build} built
                  </td>
                )
              })}
            </tr>
            {DIMENSION_ORDER.map((dimension) => (
              <tr key={dimension} className="border-b border-line last:border-b-0">
                <th scope="row" className="p-16 align-top text-[14px] font-normal text-chalk/85">
                  {DIMENSION_LABEL[dimension]}
                </th>
                {options.map((option) => {
                  const entry = option.comparison.find((c) => c.dimension === dimension)
                  const rating = entry?.rating ?? 'unknown'
                  return (
                    <td key={option.id} className={`p-16 align-top ${option.id === selectedId ? 'bg-soot/50' : ''}`}>
                      <span className={`inline-flex h-22 items-center rounded-pill px-10 font-code text-[11px] uppercase ${RATING_STYLE[rating]}`}>{RATING_LABEL[rating]}</span>
                      {entry && entry.note && <span className="mt-6 block text-[13px] leading-[1.5] text-smoke">{entry.note}</span>}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
