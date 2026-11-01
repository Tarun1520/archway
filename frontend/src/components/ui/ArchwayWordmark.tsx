import { useEffect, useId, useState } from 'react'

/**
 * The ARCHWAY name as a drawn emblem: carved-style capitals in polished
 * silver, with a sweeping stroke through the first A in place of its
 * crossbar, and a band of light that glides across.
 *
 * It is an SVG (a picture described by shapes) rather than styled text,
 * because SVG can do two things CSS text cannot:
 *
 *   1. Real bevelled metal. The `filter` below treats the letters as a raised
 *      surface and shines a light on it from the upper left, so edges facing
 *      the light glint and edges facing away fall into shade.
 *   2. Reshaping a letter. The first A's crossbar is cut away and the
 *      sweeping stroke is drawn in its place.
 *
 * Everything is measured in the SVG's own units (the `viewBox`), so the whole
 * emblem scales as one piece to whatever width it is given.
 *
 * THE NUMBERS
 *   The cut-out and the stroke are placed from measurements of the letter A
 *   in Cinzel at weight 600 (its crossbar sits between 0.211 and 0.250 of the
 *   font size above the baseline). They are right for that font only, so the
 *   emblem stays hidden until that font has loaded.
 */

const FONT = "'Cinzel Variable'"
const FONT_SIZE = 200
const FONT_WEIGHT = 600

/** Where the word starts, and the line the letters stand on. */
const TEXT_X = 40
const BASELINE = 190

/** The drawing area: wide enough for the word and tall enough for its shadow. */
const VIEW_WIDTH = 1122
const VIEW_HEIGHT = 240

/** The crossbar of the first A, as a four-cornered shape to cut away. */
const CROSSBAR_CUT = 'M82 139.3 L126.5 139.3 L129.7 148.5 L78.6 148.5 Z'

/**
 * The sweeping stroke: thin at both ends, thickest where it crosses the A.
 * It starts left of the A, rises gently through it, and lifts toward the R.
 * (Two curves: out along the top edge, back along the bottom edge.)
 */
const SWEEP = 'M8 160 C62 153 142 139 236 82 C150 146 66 160 8 160 Z'

export function ArchwayWordmark({ className }: { className?: string }) {
  // Ids must be unique on the page; useId makes ones that cannot clash.
  const id = useId()
  const metal = `${id}-metal`
  const glide = `${id}-glide`
  const bevel = `${id}-bevel`
  const lettersOnly = `${id}-letters`
  const withoutCrossbar = `${id}-cut`

  // Wait for the font: with any other font the cut-out would be in the wrong place.
  const [fontReady, setFontReady] = useState(false)
  useEffect(() => {
    let cancelled = false
    void document.fonts.load(`${FONT_WEIGHT} ${FONT_SIZE}px ${FONT}`).then(() => {
      if (!cancelled) {
        setFontReady(true)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const word = (
    <text x={TEXT_X} y={BASELINE} fontFamily={`${FONT}, serif`} fontSize={FONT_SIZE} fontWeight={FONT_WEIGHT}>
      ARCHWAY
    </text>
  )

  return (
    <svg
      viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
      role="img"
      aria-label="Archway"
      className={className}
      style={{ opacity: fontReady ? 1 : 0, transition: 'opacity 600ms ease' }}
    >
      <defs>
        {/* Polished metal: bright, a dark band through the middle like a reflected horizon, bright again. */}
        <linearGradient id={metal} gradientUnits="userSpaceOnUse" x1="0" y1="44" x2="0" y2="194">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="0.26" stopColor="#eceef4" />
          <stop offset="0.46" stopColor="#b9bdca" />
          <stop offset="0.54" stopColor="#7c8192" />
          <stop offset="0.64" stopColor="#c4c8d4" />
          <stop offset="1" stopColor="#f7f8fb" />
        </linearGradient>

        {/* The band of light: clear, white, clear. */}
        <linearGradient id={glide} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="0.5" stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>

        {/* A stencil of everything except the first A's crossbar. */}
        <clipPath id={withoutCrossbar}>
          <path clipRule="evenodd" d={`M0 0 H${VIEW_WIDTH} V${VIEW_HEIGHT} H0 Z ${CROSSBAR_CUT}`} />
        </clipPath>

        {/* A stencil in the shape of the letters and the sweep, so the light only shows on them. */}
        <clipPath id={lettersOnly}>
          {word}
          <path d={SWEEP} />
        </clipPath>

        {/*
          The bevel. Read top to bottom:
            - blur the shape's outline, so its edges become slopes
            - light those slopes from the upper left: a sharp glint, and a soft shade
            - darken the metal by the shade, add the glint, keep it inside the letters
            - underneath, add a thin dark edge (thickness) and a soft shadow (lift)
        */}
        <filter id={bevel} x="-4%" y="-25%" width="108%" height="165%" colorInterpolationFilters="sRGB">
          <feGaussianBlur in="SourceAlpha" stdDeviation="1.7" result="slopes" />

          <feSpecularLighting in="slopes" surfaceScale="5" specularConstant="0.85" specularExponent="24" lightingColor="#ffffff" result="glint">
            <feDistantLight azimuth="225" elevation="46" />
          </feSpecularLighting>
          <feComposite in="glint" in2="SourceAlpha" operator="in" result="glintOnLetters" />

          <feDiffuseLighting in="slopes" surfaceScale="5" diffuseConstant="1.15" lightingColor="#ffffff" result="shade">
            <feDistantLight azimuth="225" elevation="60" />
          </feDiffuseLighting>
          <feComposite in="SourceGraphic" in2="shade" operator="arithmetic" k1="1" k2="0" k3="0" k4="0" result="shaded" />
          <feComposite in="shaded" in2="SourceAlpha" operator="in" result="shadedLetters" />
          <feComposite in="glintOnLetters" in2="shadedLetters" operator="arithmetic" k1="0" k2="1" k3="1" k4="0" result="metal" />

          <feOffset in="SourceAlpha" dy="2.2" result="edgeShape" />
          <feFlood floodColor="#2b2e3a" result="edgeColor" />
          <feComposite in="edgeColor" in2="edgeShape" operator="in" result="edge" />

          <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="shadowBlur" />
          <feOffset in="shadowBlur" dy="9" result="shadowShape" />
          <feFlood floodColor="#14141e" floodOpacity="0.55" result="shadowColor" />
          <feComposite in="shadowColor" in2="shadowShape" operator="in" result="shadow" />

          <feMerge>
            <feMergeNode in="shadow" />
            <feMergeNode in="edge" />
            <feMergeNode in="metal" />
          </feMerge>
        </filter>
      </defs>

      {/* The metal letters and the sweep, bevelled as one piece. */}
      <g filter={`url(#${bevel})`}>
        <g fill={`url(#${metal})`}>
          <g clipPath={`url(#${withoutCrossbar})`}>{word}</g>
          <path d={SWEEP} />
        </g>
      </g>

      {/* The gliding light: a slanted bar that slides across, visible only on the letters. */}
      <g clipPath={`url(#${withoutCrossbar})`}>
        <g clipPath={`url(#${lettersOnly})`}>
          <rect className="wordmark-glide" x="-200" y="0" width="170" height={VIEW_HEIGHT} fill={`url(#${glide})`} />
        </g>
      </g>
    </svg>
  )
}
