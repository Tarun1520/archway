import { DirectionalLight, Group, HemisphereLight } from 'three'
import type { ScenePart } from '../scenePart'

/**
 * The lights that shape the furniture.
 *
 * (The grass and the painted backdrop color themselves in their shaders and
 * ignore these lights. The lights are here for the desk, chair and laptop.)
 */
export function createLighting(): ScenePart {
  // Light 1: the sky. Soft blue light from above, green bounce from the grass below.
  const skyLight = new HemisphereLight('#cfe0ff', '#3f5a36', 0.9)

  // Light 2: the morning sun. Warm, low, from behind and to the left, where
  // the glow is in the backdrop. It is the only light that casts shadows.
  const sun = new DirectionalLight('#ffd9b8', 2.6)
  sun.position.set(-4.5, 5.5, -3.5)
  sun.castShadow = true

  // A shadow is made by photographing the scene from the light's position.
  // These numbers say how sharp that photograph is and how much ground it covers.
  sun.shadow.mapSize.set(2048, 2048)
  sun.shadow.camera.left = -2.4
  sun.shadow.camera.right = 2.4
  sun.shadow.camera.top = 2.4
  sun.shadow.camera.bottom = -2.4
  sun.shadow.camera.near = 1
  sun.shadow.camera.far = 16
  sun.shadow.radius = 5 // soften the shadow's edge
  sun.shadow.bias = -0.0004 // prevents a striped pattern on lit surfaces

  // Light 3: a gentle fill from the viewer's side, so the sides facing us are not too dark.
  const fill = new DirectionalLight('#dfe6ff', 0.75)
  fill.position.set(2.5, 3, 8)

  const group = new Group()
  group.add(skyLight, sun, sun.target, fill)

  return {
    object: group,
    dispose() {
      sun.shadow.map?.dispose()
    },
  }
}
