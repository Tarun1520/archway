import { describe, expect, it } from 'vitest'
import { displayInsets, heroScreenTrack } from '../content/heroScreenTrack'
import { NARROW_WINDOW, hasArrived, placeOnScreen, screenRectAt, smoothstep } from './screenHandoff'

const noInsets = { left: 0, right: 0, top: 0, bottom: 0 }
const video = { width: 1280, height: 720 }

describe('smoothstep', () => {
  it('is 0 before the start, 1 after the end, and a half in the middle', () => {
    expect(smoothstep(2, 4, 1)).toBe(0)
    expect(smoothstep(2, 4, 5)).toBe(1)
    expect(smoothstep(2, 4, 3)).toBe(0.5)
  })
})

describe('screenRectAt', () => {
  const keyframes = [
    [1, 0.4, 0.4, 0.6, 0.6],
    [3, 0.2, 0.2, 0.8, 0.8],
  ] as const

  it('returns a measurement exactly at its own time', () => {
    expect(screenRectAt(1, keyframes, noInsets)).toEqual({ left: 0.4, top: 0.4, right: 0.6, bottom: 0.6 })
  })

  it('blends two measurements for a time in between', () => {
    const rect = screenRectAt(2, keyframes, noInsets)
    expect(rect.left).toBeCloseTo(0.3)
    expect(rect.right).toBeCloseTo(0.7)
  })

  it('holds the first and last measurement outside the measured range', () => {
    expect(screenRectAt(0, keyframes, noInsets).left).toBe(0.4)
    expect(screenRectAt(99, keyframes, noInsets).left).toBe(0.2)
  })

  it('trims the insets off each side', () => {
    const rect = screenRectAt(1, keyframes, { left: 0.1, right: 0.1, top: 0.5, bottom: 0 })
    expect(rect.left).toBeCloseTo(0.42) // 0.4 + 10% of the 0.2 width
    expect(rect.right).toBeCloseTo(0.58)
    expect(rect.top).toBeCloseTo(0.5) // 0.4 + 50% of the 0.2 height
    expect(rect.bottom).toBeCloseTo(0.6)
  })
})

describe('placeOnScreen', () => {
  it('shrinks the page to the width of a small display and puts it at its corner', () => {
    // A window the same shape as the video, so the video is not cropped.
    const viewport = { width: 1280, height: 720 }
    const placement = placeOnScreen({ left: 0.25, top: 0.25, right: 0.75, bottom: 0.75 }, viewport, video)

    expect(placement.scale).toBeCloseTo(0.5)
    expect(placement.x).toBeCloseTo(320)
    expect(placement.y).toBeCloseTo(180)
    expect(placement.visibleHeight).toBeCloseTo(360)
  })

  it('is exactly full size in the normal place once the display covers the window', () => {
    const viewport = { width: 1440, height: 810 }
    const placement = placeOnScreen({ left: -0.2, top: -0.3, right: 1.2, bottom: 1.3 }, viewport, video)

    expect(placement).toEqual({ scale: 1, x: 0, y: 0, visibleHeight: 810 })
  })

  it('accounts for the sides of the video being cut off in a narrower window', () => {
    // 4:3 window: the 16:9 video is scaled to the window's height and its sides overflow.
    const viewport = { width: 960, height: 720 }
    const placement = placeOnScreen({ left: 0.4, top: 0.4, right: 0.6, bottom: 0.6 }, viewport, video)

    // The display is 256 px wide in the video, which is shown at its natural size here.
    expect(placement.scale).toBeCloseTo(256 / 960)
    // The video overflows by 160 px on each side, so the display starts at 512 - 160.
    expect(placement.x).toBeCloseTo(352)
  })

  it('moves with the video when the video is drawn enlarged and shifted', () => {
    const viewport = { width: 1280, height: 720 }
    const display = { left: 0.25, top: 0.25, right: 0.75, bottom: 0.75 }
    const placement = placeOnScreen(display, viewport, video, { zoom: 2, shiftX: 10, shiftY: 5 })

    // Twice the size, measured from the middle of the top edge, after the shift.
    expect(placement.scale).toBeCloseTo(1) // 640 px wide x 2 = the full window width
    expect(placement.y).toBeCloseTo(2 * (180 + 5))
  })
})

describe('hasArrived', () => {
  const viewport = { width: 1440, height: 810 }

  it('is true only when the page fills the window at full size', () => {
    expect(hasArrived({ scale: 1, x: 0, y: 0, visibleHeight: 810 }, viewport)).toBe(true)
    expect(hasArrived({ scale: 0.5, x: 300, y: 200, visibleHeight: 400 }, viewport)).toBe(false)
    // Full width, but still only a band of the window: not arrived yet.
    expect(hasArrived({ scale: 1, x: 0, y: 120, visibleHeight: 500 }, viewport)).toBe(false)
  })
})

describe('the measured track for the current clip', () => {
  it('ends with the page filling a tall phone window too', () => {
    const viewport = { width: 375, height: 812 }
    const lastTime = heroScreenTrack[heroScreenTrack.length - 1][0]
    const display = screenRectAt(lastTime, heroScreenTrack, displayInsets)
    const placement = placeOnScreen(display, viewport, video, { zoom: NARROW_WINDOW.videoZoom, shiftX: 0, shiftY: 0 })

    expect(hasArrived(placement, viewport)).toBe(true)
  })

  it('shows the page on the laptop in the very first frame', () => {
    const display = screenRectAt(0, heroScreenTrack, displayInsets)
    const placement = placeOnScreen(display, { width: 1440, height: 810 }, video)

    expect(placement.scale).toBeGreaterThan(0.03)
    expect(placement.scale).toBeLessThan(0.06)
    expect(placement.visibleHeight).toBeGreaterThan(20)
  })

  it('has times in increasing order', () => {
    for (let index = 1; index < heroScreenTrack.length; index++) {
      expect(heroScreenTrack[index][0]).toBeGreaterThan(heroScreenTrack[index - 1][0])
    }
  })

  it('ends with the page at full size for common wide window shapes', () => {
    const lastTime = heroScreenTrack[heroScreenTrack.length - 1][0]
    const display = screenRectAt(lastTime, heroScreenTrack, displayInsets)

    for (const viewport of [
      { width: 1440, height: 810 }, // 16:9
      { width: 1728, height: 1117 }, // a laptop screen
      { width: 2560, height: 1080 }, // ultrawide
      { width: 1024, height: 768 }, // 4:3
    ]) {
      const placement = placeOnScreen(display, viewport, video)
      expect(placement).toEqual({ scale: 1, x: 0, y: 0, visibleHeight: viewport.height })
    }
  })
})
