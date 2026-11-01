import { BufferAttribute, BufferGeometry, Points, ShaderMaterial } from 'three'
import { createRandom } from '../random'
import type { ScenePart } from '../scenePart'
import { CAMERA } from '../sceneSettings'
import { hillHeight } from './hillShape'

const FLOWER_COUNT = 90

/** Flowers grow in a loose patch in front of the desk and to its right, in metres. */
const PATCH = { minX: 1.1, maxX: 5.5, minZ: 0.5, maxZ: 3.4 }

/** Diameter of a flower head, in metres. */
const FLOWER_SIZE = 0.03

const vertexShader = /* glsl */ `
  attribute float aSize;
  uniform float uPixelsPerUnit; // how many pixels one scene unit covers at distance 1

  void main() {
    vec4 viewPosition = viewMatrix * vec4(position, 1.0);
    // Farther flowers are drawn smaller: size divided by distance.
    gl_PointSize = aSize * uPixelsPerUnit / -viewPosition.z;
    gl_Position = projectionMatrix * viewPosition;
  }
`

const fragmentShader = /* glsl */ `
  precision highp float;

  void main() {
    // A point is drawn as a square. Throw away the corners to make it round.
    float fromCenter = length(gl_PointCoord - 0.5);
    if (fromCenter > 0.5) discard;

    // Pale petals, slightly darker toward the rim.
    vec3 color = mix(vec3(1.0, 0.98, 0.94), vec3(0.80, 0.80, 0.76), smoothstep(0.15, 0.5, fromCenter));
    gl_FragColor = vec4(color, 1.0);
  }
`

/**
 * A scattering of small white wildflowers among the grass.
 * Each flower is a single round dot ("point"), which is very cheap to draw.
 */
export function createFlowers(): ScenePart {
  const positions = new Float32Array(FLOWER_COUNT * 3)
  const sizes = new Float32Array(FLOWER_COUNT)
  const random = createRandom(29)

  for (let index = 0; index < FLOWER_COUNT; index++) {
    // Squaring pulls flowers toward the left of the patch, so it thins out to the right.
    const x = PATCH.minX + random() * random() * (PATCH.maxX - PATCH.minX)
    const z = PATCH.minZ + random() * (PATCH.maxZ - PATCH.minZ)

    positions[index * 3] = x
    positions[index * 3 + 1] = hillHeight(x, z) + 0.2 + random() * 0.16 // just above the grass
    positions[index * 3 + 2] = z
    sizes[index] = FLOWER_SIZE * (0.6 + random() * 0.8)
  }

  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(positions, 3))
  geometry.setAttribute('aSize', new BufferAttribute(sizes, 1))

  const uniforms = { uPixelsPerUnit: { value: 1 } }
  const material = new ShaderMaterial({ uniforms, vertexShader, fragmentShader })

  const points = new Points(geometry, material)
  points.frustumCulled = false

  return {
    object: points,
    setResolution(_width, height) {
      // Perspective maths: the screen's height covers 2 * tan(fov / 2) units at distance 1.
      const fieldOfViewRadians = (CAMERA.fieldOfView * Math.PI) / 180
      uniforms.uPixelsPerUnit.value = height / (2 * Math.tan(fieldOfViewRadians / 2))
    },
    dispose() {
      geometry.dispose()
      material.dispose()
    },
  }
}
