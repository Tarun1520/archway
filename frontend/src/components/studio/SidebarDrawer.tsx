import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { studioUi } from '../../content/studio'

interface SidebarDrawerProps {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/**
 * The sidebar on screens too narrow to keep it open: it slides in from the
 * left over the page. Escape or the dimmed backdrop closes it.
 */
export function SidebarDrawer({ open, onClose, children }: SidebarDrawerProps) {
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    panel.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex lg:hidden">
      <div ref={panel} tabIndex={-1} role="dialog" aria-modal="true" aria-label={studioUi.menu} className="h-full w-full max-w-[320px] bg-void p-12 outline-none">
        {children}
      </div>
      <button type="button" aria-label={studioUi.closeProjects} className="flex-1 bg-void/70 backdrop-blur-[2px]" onClick={onClose} />
    </div>
  )
}
