import { useState } from 'react'
import { studioUi } from '../../../content/studio'
import { StudioButton } from '../StudioButton'

/**
 * "Ask for a change": a short request (for example "use fewer dependencies"). It drafts the next VERSION of the
 * option and puts it through the review gate again. Nothing is overwritten, and an earlier approval does not
 * carry over to the new version.
 */
export function ChangeBox({ onSend, working, label = studioUi.options.sendChange }: { onSend: (request: string) => void; working: boolean; label?: string }) {
  const [text, setText] = useState('')
  const send = () => {
    const request = text.trim()
    if (!request) return
    onSend(request)
    setText('')
  }
  return (
    <div className="flex max-w-2xl flex-col gap-12 rounded-card border border-line bg-carbon/70 p-16">
      <label htmlFor="option-change" className="font-code text-label uppercase text-smoke">
        {studioUi.options.askChange}
      </label>
      <textarea
        id="option-change"
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={studioUi.options.askChangePlaceholder}
        className="w-full resize-y rounded-default border border-line bg-soot/60 px-16 py-12 text-[16px] text-chalk placeholder:text-smoke focus-visible:outline-2 focus-visible:outline-vermilion"
      />
      <div className="flex flex-wrap items-center gap-16">
        <StudioButton variant="outline" disabled={working || text.trim() === ''} onClick={send}>
          {label}
        </StudioButton>
        <p className="min-w-0 flex-1 text-[13px] text-smoke">{studioUi.options.askChangeHint}</p>
      </div>
    </div>
  )
}
