import { CanvasTexture, Group, Mesh, MeshBasicMaterial, MeshStandardMaterial, PlaneGeometry, SRGBColorSpace } from 'three'
import type { BufferGeometry } from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import type { ScenePart } from '../scenePart'
import { DESK, LAPTOP } from '../sceneSettings'
import { drawKeyboard, drawStudioPreview } from './laptopScreen'
import { createAluminiumMaterial, createPlasticMaterial, disposeMaterial } from './materials'

/** Thickness of the lid (the half with the screen in it). */
const LID_THICKNESS = 0.007

/** Width of the black frame around the lit part of the screen. */
const BEZEL = 0.012

/** Makes an invisible canvas of the given size to draw a texture on. */
function createCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas
}

/**
 * The laptop on the desk: an aluminium base with a keyboard, and an open lid
 * whose screen shows a preview of the Archway studio.
 *
 * The scroll zoom ends on this screen, so it is the one part of the scene
 * people look at closely.
 */
export function createLaptop(): ScenePart {
  const laptop = new Group()
  const geometries: BufferGeometry[] = []

  const aluminium = createAluminiumMaterial()
  const bezel = createPlasticMaterial()

  // --- Base ----------------------------------------------------------------
  const baseGeometry = new RoundedBoxGeometry(LAPTOP.width, LAPTOP.baseThickness, LAPTOP.depth, 4, 0.005)
  const base = new Mesh(baseGeometry, aluminium)
  base.position.y = LAPTOP.baseThickness / 2
  base.castShadow = true
  base.receiveShadow = true
  laptop.add(base)
  geometries.push(baseGeometry)

  // The keyboard and trackpad are a drawing laid flat on top of the base.
  const keyboardCanvas = createCanvas(1040, 720)
  drawKeyboard(keyboardCanvas)
  const keyboardTexture = new CanvasTexture(keyboardCanvas)
  keyboardTexture.colorSpace = SRGBColorSpace
  keyboardTexture.anisotropy = 8

  const keyboardMaterial = new MeshStandardMaterial({ map: keyboardTexture, roughness: 0.45, metalness: 0.6 })
  const keyboardGeometry = new PlaneGeometry(LAPTOP.width - 0.008, LAPTOP.depth - 0.008)
  const keyboard = new Mesh(keyboardGeometry, keyboardMaterial)
  keyboard.rotation.x = -Math.PI / 2 // lay it flat, facing up
  keyboard.position.y = LAPTOP.baseThickness + 0.0004 // a hair above the base, so the two never flicker
  keyboard.receiveShadow = true
  laptop.add(keyboard)
  geometries.push(keyboardGeometry)

  // --- Lid -----------------------------------------------------------------
  // The lid sits in a group whose origin is the hinge, at the back edge of
  // the base. Rotating that group opens or closes the laptop.
  const hinge = new Group()
  hinge.position.set(0, LAPTOP.baseThickness, -LAPTOP.depth / 2 + 0.004)
  hinge.rotation.x = -LAPTOP.lidLean
  laptop.add(hinge)

  const lidGeometry = new RoundedBoxGeometry(LAPTOP.width, LAPTOP.lidHeight, LID_THICKNESS, 4, 0.003)
  const lid = new Mesh(lidGeometry, aluminium)
  lid.position.y = LAPTOP.lidHeight / 2
  lid.castShadow = true
  hinge.add(lid)
  geometries.push(lidGeometry)

  // The black glass covering the inside face of the lid.
  const glassGeometry = new PlaneGeometry(LAPTOP.width - 0.004, LAPTOP.lidHeight - 0.004)
  const glass = new Mesh(glassGeometry, bezel)
  glass.position.set(0, LAPTOP.lidHeight / 2, LID_THICKNESS / 2 + 0.0003)
  hinge.add(glass)
  geometries.push(glassGeometry)

  // The lit picture. "Basic" material ignores the scene's lights, which is
  // right for a screen: it makes its own light. `toneMapped: false` keeps its
  // colors exactly as drawn.
  const screenCanvas = createCanvas(1280, 800)
  drawStudioPreview(screenCanvas)
  const screenTexture = new CanvasTexture(screenCanvas)
  screenTexture.colorSpace = SRGBColorSpace
  screenTexture.anisotropy = 8

  const screenMaterial = new MeshBasicMaterial({ map: screenTexture, toneMapped: false })
  const screenWidth = LAPTOP.width - BEZEL * 2
  const screenGeometry = new PlaneGeometry(screenWidth, screenWidth * (800 / 1280))
  const screen = new Mesh(screenGeometry, screenMaterial)
  screen.position.set(0, LAPTOP.lidHeight / 2 + 0.002, LID_THICKNESS / 2 + 0.0006)
  hinge.add(screen)
  geometries.push(screenGeometry)

  // The page's font may still be loading when the screen is first drawn.
  // Draw it again once the font is ready, so the text uses the right letters.
  let disposed = false
  void document.fonts.ready.then(() => {
    if (!disposed) {
      drawStudioPreview(screenCanvas)
      screenTexture.needsUpdate = true
    }
  })

  // Stand the laptop on the desk.
  laptop.position.set(LAPTOP.position.x, DESK.topHeight, LAPTOP.position.z)

  return {
    object: laptop,
    dispose() {
      disposed = true
      for (const geometry of geometries) {
        geometry.dispose()
      }
      keyboardTexture.dispose()
      keyboardMaterial.dispose()
      screenTexture.dispose()
      screenMaterial.dispose()
      disposeMaterial(aluminium)
      disposeMaterial(bezel)
    },
  }
}
