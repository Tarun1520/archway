import { useRef, useState } from 'react'
import { motion, useScroll, useTransform } from 'motion/react'
import { heroMedia } from '../../content/heroMedia'
import { hero } from '../../content/welcome'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { ArchwayWordmark } from '../ui/ArchwayWordmark'
import { Reveal } from '../ui/Reveal'
import { HeroBackdrop } from './HeroBackdrop'
import { HeroVideoBackdrop } from './HeroVideoBackdrop'

/**
 * The first screen, and the scroll zoom that follows it.
 *
 * WHAT IS ON IT
 *   Only the name, as a large silver emblem, with a short line above its
 *   left end and another below its right end. Everything
 *   a visitor can act on (the idea form) is on the second screen, which in
 *   the video is what the laptop is showing.
 *
 * HOW THE ZOOM WORKS
 *   The <section> is a tall "track". Inside it, the hero itself is exactly
 *   one window tall and `sticky`, which means it stays pinned to the top of
 *   the window while the page scrolls through the track.
 *
 *   So for a while the page scrolls but the hero does not move. That scroll
 *   distance is turned into a number from 0 to 1 ("progress"), and the number
 *   drives everything: the camera closes in on the laptop, the name fades
 *   away, and at 1 the hero un-pins and the page carries on.
 *
 * With reduced motion on, the track is one window tall: no pinning, no zoom.
 */
export function Hero() {
  const reduceMotion = usePrefersReducedMotion()
  const trackRef = useRef<HTMLElement>(null)
  const filmed = Boolean(heroMedia.videoSrc)

  // Which copy of the clip to load: the small one on phone-sized screens.
  // Decided once (useState with a function runs it only on the first render),
  // so the clip is not swapped and reloaded if the window is resized.
  const [clipSrc] = useState(() => {
    const shorterSide = Math.min(window.screen.width, window.screen.height)
    const useSmall = Boolean(heroMedia.videoSrcSmall) && shorterSide < heroMedia.smallScreenBelow
    return useSmall ? heroMedia.videoSrcSmall : heroMedia.videoSrc
  })

  // How tall the track is, in window heights: one for the hero itself, plus
  // the scrolling distance the zoom takes.
  const trackScreens = 1 + (filmed ? heroMedia.scrollLengthInScreens : 1.5)

  // 0 when the top of the track meets the top of the window, 1 when its
  // bottom meets the bottom of the window.
  const { scrollYProgress } = useScroll({ target: trackRef, offset: ['start start', 'end end'] })

  // Each of these reads: "as progress goes from A to B, go from X to Y".
  const nameOpacity = useTransform(scrollYProgress, [0, 0.14], [1, 0])
  const nameLift = useTransform(scrollYProgress, [0, 0.14], [0, -48])
  const hintOpacity = useTransform(scrollYProgress, [0, 0.06], [1, 0])

  const fading = !reduceMotion

  return (
    <section id="top" data-fills-window ref={trackRef} className="relative" style={fading ? { height: `${trackScreens * 100}svh` } : undefined}>
      {/* `isolate` keeps the backdrop's negative z-index inside the hero. */}
      <div className="sticky top-0 isolate flex h-svh flex-col overflow-hidden">
        {/* A filmed hero if one has been provided (see content/heroMedia.ts); otherwise the live 3D scene. */}
        {filmed ? (
          <HeroVideoBackdrop trackRef={trackRef} videoSrc={clipSrc} posterSrc={heroMedia.posterSrc} />
        ) : (
          <HeroBackdrop trackRef={trackRef} />
        )}

        {/* Blurs and dims the picture toward its sides and corners (see `hero-vignette` in styles/index.css). */}
        <div aria-hidden="true" className="hero-vignette pointer-events-none absolute inset-0 -z-10" />

        {/* A dark wash over the sky keeps the name readable. It leaves with the name. */}
        <motion.div
          aria-hidden="true"
          style={fading ? { opacity: nameOpacity } : undefined}
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[62%] bg-linear-to-b from-onyx/65 via-onyx/35 to-transparent"
        />

        {/* The top padding grows with the window's height, so the name sits about a fifth of the way down. */}
        <motion.div
          style={fading ? { opacity: nameOpacity, y: nameLift } : undefined}
          className="mx-auto flex w-full max-w-page flex-col items-center px-20 pt-[clamp(112px,19svh,220px)] text-center md:px-32"
        >
          <Reveal>
            {/*
              This block is exactly as wide as the name. `self-start` puts the
              first line at the name's left end, above it; `self-end` puts the
              second at its right end, below it. Read in order they say:
              "Bring your idea / ARCHWAY / will find the path". The spacing
              above and below the name is set in styles/index.css.
            */}
            <div className="wordmark-block flex flex-col">
              <p className="wordmark-line-above wordmark-line-shadow self-start pl-[3.5%] text-wordmark-line text-white">
                {hero.lineAbove}
              </p>
              {/* The page's main heading: the name, drawn as a silver emblem. */}
              <h1>
                <ArchwayWordmark className="block h-auto w-full" />
              </h1>
              <p className="wordmark-line-below wordmark-line-shadow self-end pr-[3.5%] text-wordmark-line text-white">
                {hero.lineBelow}
              </p>
            </div>
          </Reveal>
        </motion.div>

        {/* `mt-auto` pushes the hint to the bottom of the hero, whatever its height. */}
        <motion.div
          aria-hidden="true"
          style={fading ? { opacity: hintOpacity } : undefined}
          className="mt-auto flex flex-col items-center gap-8 pb-32"
        >
          <span className="rounded-pill bg-onyx/45 px-16 py-8 text-caption font-strong text-ivory backdrop-blur-[12px]">
            {hero.scrollHint}
          </span>
          <span className="scroll-cue h-24 w-px bg-ivory" />
        </motion.div>
      </div>
    </section>
  )
}
