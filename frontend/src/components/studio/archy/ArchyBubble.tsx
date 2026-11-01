import { forwardRef } from 'react'

interface ArchyBubbleProps {
  text: string
  /** Shown (true) or faded away (false). The last text stays while it fades. */
  visible: boolean
  /** A problem (such as a blocked microphone) in the accent colour, instead of a line he is saying. */
  problem?: boolean
  /** In the normal flow of the page instead of free-floating (the narrow drawer). */
  inline?: boolean
}

/**
 * What ARCHY says, as a small speech bubble that comes out of him: a rounded
 * box in the studio's warm white, one tail pointing down at his head. The
 * parent places it (it follows him as he runs) and sets `--tail-x`, how far
 * from the bubble's left edge the tail points.
 */
export const ArchyBubble = forwardRef<HTMLDivElement, ArchyBubbleProps>(function ArchyBubble({ text, visible, problem = false, inline = false }, ref) {
  return (
    <div ref={ref} className={`pointer-events-none ${inline ? 'relative' : 'absolute top-0 left-0'}`} style={{ visibility: text ? 'visible' : 'hidden' }}>
      <p
        role="status"
        aria-hidden={!visible}
        className={`relative w-max max-w-[230px] origin-bottom rounded-[14px] px-12 py-8 text-[13px] leading-[1.4] font-medium shadow-[0_8px_24px_-8px_rgba(0,0,0,0.6)] transition-[opacity,transform] duration-200 ease-out ${
          problem ? 'bg-vermilion text-void' : 'bg-chalk text-void'
        } ${visible ? 'scale-100 opacity-100' : 'scale-95 opacity-0'}`}
      >
        {text}
        <span
          aria-hidden="true"
          className={`absolute -bottom-[5px] left-[var(--tail-x,50%)] size-10 -translate-x-1/2 rotate-45 ${problem ? 'bg-vermilion' : 'bg-chalk'}`}
        />
      </p>
    </div>
  )
})
