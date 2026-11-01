/**
 * Builds the three.js picture behind the hero: a desk, a chair and a laptop
 * on a grassy hilltop, looking out over a misty valley in the morning.
 *
 * This file knows nothing about React or the page. It takes a <canvas> and
 * returns a few functions to control the picture, so the same scene could be
 * mounted from any framework.
 *
 * It is only the assembler. Each visible thing is built by its own file and
 * follows the ScenePart contract (see scenePart.ts):
 *
 *   backdrop/createValleyBackdrop.ts   sky, mountains, river (a painted picture)
 *   foreground/createHill.ts           the ground
 *   foreground/createGrass.ts          the meadow
 *   foreground/createFlowers.ts        white wildflowers
 *   foreground/createDesk.ts           the desk and its drawers
 *   foreground/createChair.ts          the office chair
 *   foreground/createLaptop.ts         the laptop and what is on its screen
 *   foreground/createLighting.ts       sun, sky and fill lights
 *
 * three.js vocabulary:
 *   renderer  draws onto the canvas using the graphics card (WebGL)
 *   scene     the list of things to draw
 *   camera    the viewpoint
 */
import { ACESFilmicToneMapping, PCFSoftShadowMap, PerspectiveCamera, Scene, Vector2, WebGLRenderer } from 'three'
import { createValleyBackdrop } from './backdrop/createValleyBackdrop'
import { createSkyEnvironment } from './createSkyEnvironment'
import { createChair } from './foreground/createChair'
import { createDesk } from './foreground/createDesk'
import { createFlowers } from './foreground/createFlowers'
import { createGrass } from './foreground/createGrass'
import { createHill } from './foreground/createHill'
import { createLaptop } from './foreground/createLaptop'
import { createLighting } from './foreground/createLighting'
import type { ScenePart } from './scenePart'
import { CAMERA } from './sceneSettings'

/** Sharp screens have 2-3 device pixels per CSS pixel. Capping the ratio keeps drawing fast. */
const MAX_PIXEL_RATIO = 1.5

export interface HeroScene {
  /** Match the drawing size to the element's size in CSS pixels. */
  resize(width: number, height: number): void
  /** How far the scroll zoom has gone: 0 = opening shot, 1 = close-up of the laptop. */
  setZoom(progress: number): void
  /** Pointer position from -1 (left / top) to 1 (right / bottom). */
  setPointer(x: number, y: number): void
  /** Draw one frame for the given time in seconds. */
  renderFrame(timeSeconds: number): void
  /** Release the graphics memory. Call when the hero is removed. */
  dispose(): void
}

/** Blends from `from` to `to`. `amount` 0 gives `from`, 1 gives `to`. */
function mix(from: number, to: number, amount: number): number {
  return from + (to - from) * amount
}

/**
 * Turns steady progress (0 to 1) into progress that starts gently, speeds up,
 * and settles gently. Camera moves feel mechanical without this.
 */
function easeInOut(progress: number): number {
  return progress * progress * (3 - 2 * progress)
}

/**
 * Throws if the browser cannot create a WebGL context. The caller catches
 * that and leaves the plain CSS background in place.
 */
export function createHeroScene(canvas: HTMLCanvasElement): HeroScene {
  const renderer = new WebGLRenderer({
    canvas,
    antialias: true, // smooth the edges of the grass and the furniture
    alpha: false,
    powerPreference: 'high-performance',
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO))

  // Real shadows, with soft edges.
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = PCFSoftShadowMap

  // "Tone mapping" squeezes very bright light into the range a screen can
  // show, the way a film camera does, so highlights roll off instead of
  // turning into flat white patches.
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05

  // The plug-and-play list. Add, remove or reorder parts here.
  const parts: ScenePart[] = [
    createValleyBackdrop(),
    createHill(),
    createGrass(),
    createFlowers(),
    createLighting(),
    createDesk(),
    createChair(),
    createLaptop(),
  ]

  const scene = new Scene()
  for (const part of parts) {
    scene.add(part.object)
  }

  // What the chrome and aluminium reflect.
  const environment = createSkyEnvironment(renderer)
  scene.environment = environment.texture

  const camera = new PerspectiveCamera(CAMERA.fieldOfView, 1, 0.05, 120)
  const drawingSize = new Vector2()
  const pointer = { x: 0, y: 0 }
  let zoom = 0

  /** Places the camera for the current screen shape, zoom and pointer. */
  const placeCamera = () => {
    // 0 on a wide screen, 1 on a tall phone screen.
    const tallness = Math.min(Math.max((1.2 - camera.aspect) / 0.75, 0), 1)
    const eased = easeInOut(zoom)

    // On tall screens the camera stands farther back so nothing is cropped,
    // and aims higher at the start so the desk sits below the text.
    const startDistance = CAMERA.start.distance * mix(1, CAMERA.tallScreen.startDistanceScale, tallness)
    const endDistance = CAMERA.end.distance * mix(1, CAMERA.tallScreen.endDistanceScale, tallness)
    const startLookAt = CAMERA.start.lookAtHeight + tallness * CAMERA.tallScreen.extraLookAtHeight

    // The pointer moves the camera a little. The effect fades during the
    // zoom, because up close a small move would swing the view wildly.
    const drift = 1 - eased * 0.85

    camera.position.set(
      pointer.x * CAMERA.pointerDrift.x * drift,
      mix(CAMERA.start.height, CAMERA.end.height, eased) - pointer.y * CAMERA.pointerDrift.y * drift,
      mix(startDistance, endDistance, eased),
    )
    camera.lookAt(0, mix(startLookAt, CAMERA.end.lookAtHeight, eased), 0)
  }

  return {
    resize(width, height) {
      // `false` = do not touch the canvas's CSS size; the stylesheet owns that.
      renderer.setSize(width, height, false)
      renderer.getDrawingBufferSize(drawingSize)

      camera.aspect = width / Math.max(height, 1)
      camera.updateProjectionMatrix()

      for (const part of parts) {
        part.setResolution?.(drawingSize.x, drawingSize.y)
      }
    },
    setZoom(progress) {
      zoom = Math.min(Math.max(progress, 0), 1)
      const eased = easeInOut(zoom)
      for (const part of parts) {
        part.setZoom?.(eased)
      }
    },
    setPointer(x, y) {
      pointer.x = x
      pointer.y = y
      for (const part of parts) {
        part.setPointer?.(x, y)
      }
    },
    renderFrame(timeSeconds) {
      for (const part of parts) {
        part.update?.(timeSeconds)
      }
      placeCamera()
      renderer.render(scene, camera)
    },
    dispose() {
      for (const part of parts) {
        part.dispose()
      }
      environment.dispose()
      renderer.dispose()
    },
  }
}
