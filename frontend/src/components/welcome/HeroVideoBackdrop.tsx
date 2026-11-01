import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'
import { pointerNudgeFades } from '../../content/heroMedia'
import { heroClipFramesPerSecond } from '../../content/heroScreenTrack'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { heroPlayback } from '../../lib/heroPlayback'
import { NARROW_WINDOW, isNarrowWindow, smoothstep } from '../../lib/screenHandoff'
import { trackProgress } from '../../lib/trackProgress'

/** How quickly the clip catches up with the scroll position each frame (0 = never, 1 = instantly). */
const SCRUB_EASING = 0.18

/** How quickly the picture follows the pointer each frame. */
const POINTER_EASING = 0.05

/** How far the picture shifts with the pointer, in pixels. It is drawn slightly enlarged so its edges never show. */
const POINTER_SHIFT = { x: 14, y: 8 }
const ENLARGE = 0.04

interface HeroVideoBackdropProps {
  /** The tall section the hero is pinned inside. Scrolling through it moves the clip. */
  trackRef: RefObject<HTMLElement | null>
  videoSrc: string
  posterSrc: string
}

/**
 * A filmed hero: a clip that is never "played". Instead, the frame shown is
 * chosen from the scroll position, so scrolling down moves the film forward
 * and scrolling up moves it backward. This is called "scrubbing".
 *
 * WHY THE CLIP IS PAINTED ONTO A CANVAS
 *   The <video> element is kept out of sight and used only to decode frames.
 *   What you see is a <canvas> that each decoded frame is copied onto.
 *
 *   The reason is timing. The page drawn on the laptop's screen (see
 *   ScreenHandoff.tsx) has to move at the exact instant the picture does. A
 *   <video> shows its new frame whenever the browser gets round to it, which
 *   can be a moment before or after the page moves, and that makes the page
 *   shake against the laptop. Copying the frame to the canvas ourselves means
 *   we know precisely which frame is on screen, and the page is placed for
 *   that same frame, in the same breath.
 *
 * For the same reason the clip only ever shows whole frames (it has 24 a
 * second): the page is positioned from measurements taken frame by frame.
 *
 * A clip is a flat picture, so it cannot turn in 3D with the pointer. It
 * shifts a few pixels instead, which gives a small sense of depth.
 *
 * With reduced motion on, the clip stays on its first frame.
 */
export function HeroVideoBackdrop({ trackRef, videoSrc, posterSrc }: HeroVideoBackdropProps) {
  const stageRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const reduceMotion = usePrefersReducedMotion()

  useEffect(() => {
    const stage = stageRef.current
    const video = videoRef.current
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (!stage || !video || !canvas || !context) {
      return
    }

    let frameId = 0
    let shownTime = 0 // where in the clip we are easing toward, in seconds
    let requestedFrame = -1 // the frame number last asked of the video
    let frameIsReady = false // the video has finished decoding that frame
    const pointerTarget = { x: 0, y: 0 }
    const pointer = { x: 0, y: 0 }

    // The video tells us when the frame we asked for has been decoded.
    const onFrameDecoded = () => {
      frameIsReady = true
    }
    // "loadeddata" is the first frame arriving; "seeked" is each one after.
    video.addEventListener('loadeddata', onFrameDecoded)
    video.addEventListener('seeked', onFrameDecoded)

    const tick = () => {
      frameId = requestAnimationFrame(tick)

      heroPlayback.stageWidth = stage.clientWidth
      heroPlayback.stageHeight = stage.clientHeight

      // Nothing can be drawn until the browser has read the start of the file.
      const loaded = Number.isFinite(video.duration) && video.duration > 0 && video.videoWidth > 0
      if (loaded) {
        const lastFrame = Math.max(Math.round(video.duration * heroClipFramesPerSecond) - 1, 0)

        // 1. If the frame asked for last time has been decoded, copy it to
        //    the canvas and announce it. ScreenHandoff runs right after this,
        //    in the same animation frame, and places the page for it.
        if (frameIsReady) {
          frameIsReady = false
          if (canvas.width !== video.videoWidth) {
            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
          }
          context.drawImage(video, 0, 0, canvas.width, canvas.height)

          heroPlayback.time = Math.max(requestedFrame, 0) / heroClipFramesPerSecond
          heroPlayback.duration = video.duration
          heroPlayback.width = video.videoWidth
          heroPlayback.height = video.videoHeight
        }

        // 2. Work out which frame the scroll position calls for, and ask for
        //    it. Never while the previous request is still being decoded:
        //    piling up requests is what makes scrubbing stutter.
        const progress = reduceMotion ? 0 : trackProgress(trackRef.current, stage.clientHeight)
        shownTime += (progress * video.duration - shownTime) * SCRUB_EASING
        const wantedFrame = Math.min(Math.max(Math.floor(shownTime * heroClipFramesPerSecond + 0.001), 0), lastFrame)

        if (wantedFrame !== requestedFrame && !video.seeking) {
          requestedFrame = wantedFrame
          // Aim for the middle of the frame's time slot, so rounding can never land on its neighbour.
          video.currentTime = (wantedFrame + 0.5) / heroClipFramesPerSecond
        }
      }

      // The pointer nudges the picture, but only in the opening part of the
      // clip. It fades to nothing before the laptop's screen gets large.
      const nudge = reduceMotion ? 0 : 1 - smoothstep(pointerNudgeFades.from, pointerNudgeFades.to, heroPlayback.time)
      pointer.x += (pointerTarget.x - pointer.x) * POINTER_EASING
      pointer.y += (pointerTarget.y - pointer.y) * POINTER_EASING
      const shiftX = -pointer.x * POINTER_SHIFT.x * nudge
      const shiftY = -pointer.y * POINTER_SHIFT.y * nudge

      // On a phone held upright, draw the picture larger so the desk sits
      // lower. (`origin-top` on the canvas makes it grow downward.)
      const narrow = isNarrowWindow({ width: stage.clientWidth, height: stage.clientHeight })
      const zoom = (narrow ? NARROW_WINDOW.videoZoom : 1) + ENLARGE * nudge
      canvas.style.transform = `scale(${zoom}) translate3d(${shiftX}px, ${shiftY}px, 0)`

      // Share it, so the page drawn on the laptop's screen can move the same way.
      heroPlayback.zoom = zoom
      heroPlayback.shiftX = shiftX
      heroPlayback.shiftY = shiftY
    }

    const onPointerMove = (event: PointerEvent) => {
      pointerTarget.x = (event.clientX / window.innerWidth) * 2 - 1
      pointerTarget.y = (event.clientY / window.innerHeight) * 2 - 1
    }

    // Some phones (iPhones in particular) will not decode a video's frames
    // until it has been started once by a touch. Starting and pausing it on
    // the first touch is enough; nothing visible happens.
    const wakeVideo = () => {
      video
        .play()
        .then(() => video.pause())
        .catch(() => {
          // Refused (for example in a power-saving mode). The poster image stays.
        })
    }

    window.addEventListener('pointermove', onPointerMove, { passive: true })
    window.addEventListener('touchstart', wakeVideo, { once: true, passive: true })
    frameId = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(frameId)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('touchstart', wakeVideo)
      video.removeEventListener('loadeddata', onFrameDecoded)
      video.removeEventListener('seeked', onFrameDecoded)
      heroPlayback.duration = 0 // nothing is showing any more
    }
  }, [reduceMotion, trackRef])

  return (
    <div
      ref={stageRef}
      aria-hidden="true"
      className="hero-fallback absolute inset-0 -z-10 overflow-hidden bg-cover bg-center"
      // The clip's first frame, as a still image, shows until the clip itself is ready.
      style={posterSrc ? { backgroundImage: `url(${posterSrc})` } : undefined}
    >
      {/* What you see: each decoded frame is copied here. `object-cover` makes it fill the hero like a background photo. */}
      <canvas ref={canvasRef} className="size-full origin-top object-cover" />

      {/*
        The decoder: in the page (phones require that) but out of sight.
        muted + playsInline: required by phones before a video may load inline.
        preload="auto": fetch the whole file up front, so any frame can be shown at once.
      */}
      <video
        ref={videoRef}
        src={videoSrc}
        muted
        playsInline
        preload="auto"
        className="pointer-events-none absolute top-0 left-0 size-px opacity-0"
      />
    </div>
  )
}
