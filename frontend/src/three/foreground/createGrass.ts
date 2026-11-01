import {
  DoubleSide,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  Mesh,
  PlaneGeometry,
  ShaderMaterial,
} from 'three'
import { createRandom } from '../random'
import type { ScenePart } from '../scenePart'
import { CHAIR } from '../sceneSettings'
import { grassFragmentShader, grassVertexShader } from './grassShaders.glsl'
import { hillHeight } from './hillShape'

/** How many blades to draw. More looks lusher and costs more to draw. */
const BLADE_COUNT = 100_000

/** The patch of hill that gets grass, in metres. */
const AREA = { minX: -8, maxX: 8, minZ: -6.5, maxZ: 4.2 }

/** Grass within this distance of the furniture is shorter, as if walked on. */
const TRODDEN_RADIUS = 1.25

/**
 * The meadow: over a hundred thousand blades of grass, swaying in the wind.
 *
 * Drawing that many separate objects would be far too slow. Instead this uses
 * "instancing": the graphics card is given ONE blade shape plus a list of
 * small records (where each blade stands, how tall, which way it faces), and
 * draws them all in a single step.
 */
export function createGrass(): ScenePart {
  // One blade: a thin upright strip, split into 2 segments so it can bend.
  const blade = new PlaneGeometry(1, 1, 1, 2)

  const geometry = new InstancedBufferGeometry()
  geometry.index = blade.index
  geometry.setAttribute('position', blade.attributes.position)
  geometry.setAttribute('uv', blade.attributes.uv)
  geometry.instanceCount = BLADE_COUNT

  // The per-blade records. Each is a flat list of numbers: 3 per blade for
  // the position, 4 per blade for its other properties.
  const offsets = new Float32Array(BLADE_COUNT * 3)
  const blades = new Float32Array(BLADE_COUNT * 4)
  const random = createRandom(11)

  for (let index = 0; index < BLADE_COUNT; index++) {
    const x = AREA.minX + random() * (AREA.maxX - AREA.minX)
    const z = AREA.minZ + random() * (AREA.maxZ - AREA.minZ)

    offsets[index * 3] = x
    offsets[index * 3 + 1] = hillHeight(x, z)
    offsets[index * 3 + 2] = z

    // Most blades are short; a few are tall (cubing a 0-1 number does that).
    const tallness = random()
    let height = 0.13 + 0.16 * random() + 0.24 * tallness * tallness * tallness

    // Shorter around the desk and the chair, where feet and wheels have been.
    const toDesk = Math.hypot(x, z)
    const toChair = Math.hypot(x - CHAIR.position.x, z - CHAIR.position.z)
    const nearest = Math.min(toDesk, toChair + 0.3)
    if (nearest < TRODDEN_RADIUS) {
      height *= 0.45 + 0.55 * (nearest / TRODDEN_RADIUS)
    }

    blades[index * 4] = height
    // Facing angle: within 50 degrees of facing the viewer, so few are edge-on.
    blades[index * 4 + 1] = (random() - 0.5) * 1.75
    blades[index * 4 + 2] = random()
    blades[index * 4 + 3] = random()
  }

  geometry.setAttribute('aOffset', new InstancedBufferAttribute(offsets, 3))
  geometry.setAttribute('aBlade', new InstancedBufferAttribute(blades, 4))

  const uniforms = {
    uTime: { value: 0 },
  }

  const material = new ShaderMaterial({
    uniforms,
    vertexShader: grassVertexShader,
    fragmentShader: grassFragmentShader,
    side: DoubleSide, // a blade is visible from the front and the back
  })

  const mesh = new Mesh(geometry, material)
  // three.js would otherwise hide the whole meadow when the single blade
  // shape at the origin leaves the camera's view.
  mesh.frustumCulled = false

  return {
    object: mesh,
    update(timeSeconds) {
      uniforms.uTime.value = timeSeconds
    },
    dispose() {
      blade.dispose()
      geometry.dispose()
      material.dispose()
    },
  }
}
