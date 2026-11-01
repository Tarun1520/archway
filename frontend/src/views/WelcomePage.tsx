import { Footer } from '../components/layout/Footer'
import { TopNav } from '../components/layout/TopNav'
import { BuildPack } from '../components/welcome/BuildPack'
import { ClosingCta } from '../components/welcome/ClosingCta'
import { Hero } from '../components/welcome/Hero'
import { Features } from '../components/welcome/Features'
import { Figures } from '../components/welcome/Figures'
import { Journey } from '../components/welcome/Journey'
import { ScreenHandoff } from '../components/welcome/ScreenHandoff'
import { StartSection } from '../components/welcome/StartSection'
import { Statement } from '../components/welcome/Statement'
import { WordBand } from '../components/welcome/WordBand'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { START_HREF, focusIdeaInput } from '../lib/focusIdeaInput'
import { useSmoothScroll } from '../hooks/useSmoothScroll'

/**
 * The welcome page: the first thing a visitor sees.
 *
 * A "view" is a whole screen. It contains no styling or wording of its own;
 * it only decides which sections appear and in what order. To reorder the
 * page or remove a section, edit the list inside <main>.
 */
export function WelcomePage() {
  const reduceMotion = usePrefersReducedMotion()
  useSmoothScroll(!reduceMotion)

  return (
    <>
      {/* Hidden until focused: lets keyboard users jump past the navigation. */}
      <a
        href={START_HREF}
        onClick={focusIdeaInput}
        className="sr-only focus:not-sr-only focus:fixed focus:top-12 focus:left-12 focus:z-[60] focus:rounded-pill focus:bg-graphite focus:px-16 focus:py-8 focus:text-ivory"
      >
        Skip to content
      </a>

      <TopNav />

      <main>
        <Hero />

        {/* Everything after the hero arrives through the laptop's screen. */}
        <ScreenHandoff>
          <StartSection />
          <Statement />
          <Journey />
          <WordBand />
          <Figures />
          <Features />
          <BuildPack />
          <ClosingCta />
        </ScreenHandoff>
      </main>

      <Footer />
    </>
  )
}
