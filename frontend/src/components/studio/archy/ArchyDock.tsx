import { useEffect, useState } from 'react'
import { archyUi } from '../../../content/archy'
import type { Archy } from '../../../hooks/useArchy'
import { ArchyPortal } from './ArchyPortal'
import { ArchyStage3D } from './ArchyStage3D'

interface ArchyDockProps {
  archy: Archy
  /** False when the backend has no voice key: the portal stays dark and says why. */
  available: boolean
  /** Whether he plays tricks in the air while he waits. */
  tricks: boolean
  /** True in the phone-sized drawer, where there is no room to run: his stage is then small and inside the drawer. */
  inDrawer?: boolean
  /** True on a wide screen (the strip layout is for those). */
  wide: boolean
  /** The slim folded sidebar: only a small portal, which opens the sidebar and wakes Archy. */
  compact?: boolean
  onExpand?: () => void
}

/**
 * Archy's home, under the sidebar: a portal. Clicking it wakes Archy, who
 * rises out of it on a column of air, floats there introducing himself and listening
 * for the idea, and plays in the air when he is quiet. Clicking the portal again
 * (or Archy himself) sends him back.
 *
 * Nothing is drawn around him. The dock is pinned to the bottom-left corner
 * of the window. What Archy says comes out of him as a small speech bubble
 * (ArchyBubble); what the person says is typed into the chat box in the
 * workspace, and every setting is in the Voice view.
 */
export function ArchyDock({ archy, available, tricks, inDrawer = false, wide, compact = false, onExpand }: ArchyDockProps) {
  const awake = archy.phase !== 'off' && archy.phase !== 'leaving'
  const toggle = () => (awake ? archy.deactivate() : archy.activate())

  // The bubble shows while he speaks and a moment after, then fades. A problem stays until it is gone.
  const [lingering, setLingering] = useState(false)
  useEffect(() => {
    if (archy.speaking) {
      setLingering(true)
      return
    }
    const timer = window.setTimeout(() => setLingering(false), 1600)
    return () => window.clearTimeout(timer)
  }, [archy.speaking, archy.line])
  const bubble = {
    text: awake ? (archy.problem ?? archy.line ?? '') : '',
    visible: awake && (Boolean(archy.problem) || archy.speaking || lingering),
    problem: Boolean(archy.problem),
  }

  if (compact) {
    return (
      <button
        type="button"
        disabled={!available}
        onClick={() => {
          onExpand?.()
          if (!awake) archy.activate()
        }}
        aria-label={archyUi.activate}
        title={available ? archyUi.activate : archyUi.notSetUp}
        className="mt-auto flex w-full items-center justify-center py-8 disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-vermilion"
      >
        <ArchyPortal active={awake} className="w-[52px]" />
      </button>
    )
  }

  const strip = wide && !inDrawer
  return (
    <section aria-label={`${archyUi.name}, ${archyUi.role}`} className="mt-auto flex shrink-0 flex-col px-4">
      <ArchyStage3D
        awake={awake}
        action={archy.action}
        micLevel={archy.level}
        tricks={tricks}
        strip={strip}
        height={strip ? 150 : awake ? 232 : 150}
        bubble={bubble}
        onBack={archy.deactivate}
        className="transition-[height] duration-500"
      >
        {/* The portal is the on/off button. */}
        <button
          type="button"
          disabled={!available}
          onClick={toggle}
          aria-pressed={awake}
          aria-label={awake ? archyUi.portalOn : archyUi.portalOff}
          className="absolute inset-x-[12%] bottom-0 h-[42%] rounded-pill disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-vermilion"
        />

        {/* Off: the invitation, above the portal. */}
        {!awake && (
          <button
            type="button"
            disabled={!available}
            onClick={toggle}
            className="archy-invite absolute inset-x-0 top-0 mx-auto w-fit rounded-pill border border-[#7fe8ff]/35 bg-[#0b1636]/70 px-12 py-6 text-[12.5px] font-medium text-[#cfefff] transition-colors hover:border-[#7fe8ff]/70 hover:text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-vermilion"
          >
            {archyUi.activate}
          </button>
        )}
      </ArchyStage3D>

      {!available && <p className="mt-8 text-[12px] leading-[1.5] text-smoke">{archyUi.notSetUp}</p>}
    </section>
  )
}
