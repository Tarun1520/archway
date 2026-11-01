import { studioCopy } from '../../content/studio'
import type { EvidenceItem } from '../../lib/api/types'
import { formatWhen, safeHref, shortHash, sourceLabel } from '../../lib/research'
import { AlertIcon } from '../ui/icons'
import { EmptyNote, Panel } from './Panel'

interface EvidencePanelProps {
  evidence: EvidenceItem[]
  selectedId: string | null
  onSelect: (id: string | null) => void
}

/**
 * The evidence drawer: pick any source and see exactly what was retrieved.
 *
 * For the chosen item it shows the address, when it was retrieved, the short
 * excerpt and where in the source it came from, a fingerprint of the content,
 * and, if the fetch failed, why. Failed items have no excerpt, by design.
 */
export function EvidencePanel({ evidence, selectedId, onSelect }: EvidencePanelProps) {
  const selected = evidence.find((item) => item.id === selectedId) ?? null

  return (
    <Panel heading={studioCopy.evidenceHeading} aside={<span className="font-mono text-caption text-ash">{evidence.length}</span>}>
      {evidence.length === 0 ? (
        <EmptyNote>{studioCopy.evidenceEmpty}</EmptyNote>
      ) : (
        <div className="flex flex-col gap-12">
          <ul className="flex max-h-160 flex-col gap-4 overflow-y-auto" aria-label="All evidence">
            {evidence.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  aria-pressed={item.id === selectedId}
                  onClick={() => onSelect(item.id === selectedId ? null : item.id)}
                  className={`w-full rounded-default px-8 py-6 text-left text-caption ${
                    item.id === selectedId ? 'bg-ivory/10 text-ivory' : 'text-ash hover:bg-ivory/5 hover:text-ivory'
                  }`}
                >
                  <span className="text-ivory">{sourceLabel(item.source_type)}</span>
                  <span className="block break-all">{item.repo ?? item.url}</span>
                </button>
              </li>
            ))}
          </ul>

          {selected ? (
            <article className="flex flex-col gap-8 border-t border-mist/10 pt-12 text-body-sm" aria-label="Selected evidence">
              <h3 className="text-caption font-strong tracking-wide text-ash uppercase">{sourceLabel(selected.source_type)}</h3>
              <p className="break-all">
                {safeHref(selected.url) ? (
                  <a href={safeHref(selected.url) ?? undefined} target="_blank" rel="noopener noreferrer" className="underline decoration-ivory/40 underline-offset-4">
                    {selected.url}
                  </a>
                ) : (
                  selected.url
                )}
              </p>
              <p className="text-caption text-ash">
                {studioCopy.provenanceRetrieved} {formatWhen(selected.retrieved_at)}
                {selected.mode === 'fixture' && ` · ${studioCopy.fixtureData}`}
              </p>
              {selected.extraction_status === 'failed' ? (
                <p className="flex items-start gap-6 text-ivory">
                  <span className="mt-2 shrink-0">
                    <AlertIcon size={14} />
                  </span>
                  {studioCopy.notRetrieved}: {selected.note ?? studioCopy.evidenceNoReason}
                </p>
              ) : (
                <>
                  {selected.excerpt ? (
                    <blockquote className="border-l-2 border-ivory/40 pl-12 whitespace-pre-wrap text-ivory">{selected.excerpt}</blockquote>
                  ) : (
                    <p className="text-ash italic">{studioCopy.evidenceNoExcerpt}</p>
                  )}
                  {selected.excerpt_location && (
                    <p className="text-caption text-ash">
                      {studioCopy.evidenceLocation}: {selected.excerpt_location}
                    </p>
                  )}
                  {selected.note && <p className="text-caption text-ash">{selected.note}</p>}
                </>
              )}
              {shortHash(selected.content_hash) && (
                <p className="font-mono text-caption text-ash">
                  {studioCopy.evidenceHash}: {shortHash(selected.content_hash)}
                </p>
              )}
            </article>
          ) : (
            <EmptyNote>{studioCopy.evidencePick}</EmptyNote>
          )}
        </div>
      )}
    </Panel>
  )
}
