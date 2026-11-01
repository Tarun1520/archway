import { useCallback, useEffect, useRef, useState } from 'react'
import { CurtainContext } from '../../hooks/useCurtain'
import type { ReactNode } from 'react'
import { spaceTransition } from '../../content/spaceTransition'
import { GoToWorkspaceContext } from '../../hooks/useGoToWorkspace'
import { useAuth } from '../../hooks/useAuth'
import { LOGIN_HASH, STUDIO_HASH, screenFromHash, type Screen } from '../../lib/hashRoute'

type Phase = 'idle' | 'playing' | 'leaving'

/**
 * The space transition: a full-screen film, with sound, that plays on the way
 * from the welcome page into the workspace.
 *
 *   1. "Start a project" or "Continue in workspace" calls goToWorkspace().
 *   2. The film starts playing straight away, INSIDE that click: browsers only
 *      let a page start sound in direct answer to something the person did.
 *      If sound is still refused, it plays silently instead.
 *   3. Once it is playing, the address changes to the workspace, so the
 *      workspace loads underneath, hidden by the film.
 *   4. Just before the end the film fades out and the workspace shows through.
 *
 * Signed out, "Start a project" and "Continue in workspace" lead to the sign-in page instead; signing in there
 * calls goToWorkspace() again, and the film plays from there.
 *
 * "Skip" (or Escape) fades the picture and the sound out at once. People who
 * asked their system for reduced motion go straight to the workspace.
 *
 * It wraps the whole app (App.tsx), so it stays on screen while the page
 * underneath changes from the welcome page to the workspace.
 */
export function SpaceTransition({ screen, children }: { screen: Screen; children: ReactNode }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const skipRef = useRef<HTMLButtonElement>(null)
  const [phase, setPhaseState] = useState<Phase>('idle')
  const phaseRef = useRef<Phase>('idle') // the same value, readable inside event handlers without waiting for a redraw
  const [fadeSeconds, setFadeSeconds] = useState(spaceTransition.revealSeconds)

  const setPhase = (next: Phase) => {
    phaseRef.current = next
    setPhaseState(next)
  }

  const openWorkspace = () => {
    if (screenFromHash(window.location.hash) === 'studio') return
    window.scrollTo(0, 0)
    window.location.hash = STUDIO_HASH
  }

  // Read inside the click handler below, which is created once: a ref always holds the current answer.
  const auth = useAuth()
  const signedOut = useRef(false)
  // Not signed in, or the backend cannot be reached to check: the sign-in page first (it says if the backend is down).
  signedOut.current = auth.status === 'signedOut' || auth.status === 'unreachable'

  const goToWorkspace = useCallback(() => {
    if (signedOut.current) {
      // Not signed in: the sign-in page first (it calls goToWorkspace again once the person is in).
      window.scrollTo(0, 0)
      window.location.hash = LOGIN_HASH
      return
    }
    const video = videoRef.current
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (phaseRef.current !== 'idle') return // already on its way
    if (!video || reducedMotion) {
      openWorkspace()
      return
    }
    video.currentTime = 0
    video.muted = false
    video.volume = 1
    setFadeSeconds(spaceTransition.revealSeconds)
    setPhase('playing')
    // play() must be called here, inside the click, for the sound to be allowed.
    video
      .play()
      .catch(() => {
        video.muted = true // sound refused: play without it
        return video.play()
      })
      .then(openWorkspace, () => {
        // The film cannot play at all (missing file, unsupported): just go.
        setPhase('idle')
        openWorkspace()
      })
  }, [])

  // Fades the film (and its sound) out over `seconds`, then puts it away.
  const leave = useCallback((seconds: number) => {
    if (phaseRef.current !== 'playing') return
    setFadeSeconds(seconds)
    setPhase('leaving')
    const video = videoRef.current
    if (video && !video.muted) {
      const startVolume = video.volume
      const started = performance.now()
      const step = (now: number) => {
        // The first frame's time can be a hair BEFORE `started`, which would make `left` slightly above 1 and the
        // volume above the allowed maximum (the browser throws): so it is kept between 0 and 1.
        const left = Math.min(1, Math.max(0, 1 - (now - started) / (seconds * 1000)))
        video.volume = startVolume * left
        if (left > 0) requestAnimationFrame(step)
      }
      requestAnimationFrame(step)
    }
    window.setTimeout(() => {
      videoRef.current?.pause()
      setPhase('idle')
      openWorkspace() // in case Skip was pressed before the film had started
    }, seconds * 1000 + 80)
  }, [])

  // Escape skips; the Skip button gets focus so the keyboard can reach it.
  useEffect(() => {
    if (phase !== 'playing') return
    skipRef.current?.focus({ preventScroll: true })
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') leave(spaceTransition.skipSeconds)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase, leave])

  // Start the reveal `revealSeconds` before the end. The browser reports the
  // time on every frame drawn (requestVideoFrameCallback), which is exact;
  // the older "timeupdate" event below is the fallback, and only arrives a
  // few times a second.
  const nearTheEnd = (video: HTMLVideoElement, time: number) => video.duration - time <= spaceTransition.revealSeconds
  useEffect(() => {
    const video = videoRef.current
    if (phase !== 'playing' || !video || !('requestVideoFrameCallback' in video)) return
    let handle = 0
    const onFrame = (_now: number, frame: VideoFrameCallbackMetadata) => {
      if (nearTheEnd(video, frame.mediaTime)) leave(spaceTransition.revealSeconds)
      else handle = video.requestVideoFrameCallback(onFrame)
    }
    handle = video.requestVideoFrameCallback(onFrame)
    return () => video.cancelVideoFrameCallback(handle)
  }, [phase, leave])

  const onTimeUpdate = () => {
    const video = videoRef.current
    if (video && nearTheEnd(video, video.currentTime)) leave(spaceTransition.revealSeconds)
  }

  // The film is kept ready where it can start (the welcome page and the sign-in page), and while it plays.
  const mounted = screen === 'welcome' || screen === 'login' || phase !== 'idle'

  return (
    <GoToWorkspaceContext.Provider value={goToWorkspace}>
      {/* While the film covers the page, the workspace under it knows (the agents wait to come on until it lifts). */}
      <CurtainContext.Provider value={phase === 'playing'}>{children}</CurtainContext.Provider>
      {mounted && (
        <div
          role="dialog"
          aria-label={spaceTransition.label}
          aria-hidden={phase === 'idle'}
          className={`fixed inset-0 z-[100] bg-[#000] transition-opacity ease-out ${
            phase === 'playing' ? 'opacity-100' : 'pointer-events-none opacity-0'
          } ${phase === 'idle' ? 'invisible' : ''}`}
          style={{ transitionDuration: phase === 'leaving' ? `${fadeSeconds}s` : '0.25s' }}
        >
          <video
            ref={videoRef}
            src={spaceTransition.src}
            preload="auto"
            playsInline
            aria-hidden="true"
            onTimeUpdate={onTimeUpdate}
            onEnded={() => leave(0.2)}
            className="h-full w-full object-cover"
          />
          <button
            ref={skipRef}
            type="button"
            onClick={() => leave(spaceTransition.skipSeconds)}
            tabIndex={phase === 'playing' ? 0 : -1}
            className="absolute right-24 bottom-24 flex h-44 items-center gap-8 rounded-pill border border-white/35 bg-[#000]/35 px-20 text-[15px] font-medium text-white backdrop-blur-md transition-colors hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            {spaceTransition.skipLabel}
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 5l8 7-8 7M15 5v14" />
            </svg>
          </button>
        </div>
      )}
    </GoToWorkspaceContext.Provider>
  )
}
