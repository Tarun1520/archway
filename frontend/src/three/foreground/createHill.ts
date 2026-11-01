import { Mesh, MeshBasicMaterial, PlaneGeometry } from 'three'
import type { ScenePart } from '../scenePart'
import { hillHeight } from './hillShape'

/** Size of the ground, in metres. Wide enough for very wide screens. */
const WIDTH = 30
const DEPTH = 16

/** The ground starts well behind the desk and runs toward the viewer. */
const BACK_EDGE = -8

/**
 * The ground under the grass: a dark green sheet bent into the shape of the
 * hill. Almost none of it is visible. Its job is to fill the gaps between
 * blades of grass so the backdrop never shows through them.
 */
export function createHill(): ScenePart {
  // A flat grid of points, laid on the ground and then lifted to the hill's shape.
  const geometry = new PlaneGeometry(WIDTH, DEPTH, 150, 80)
  geometry.rotateX(-Math.PI / 2) // from standing upright to lying flat
  geometry.translate(0, 0, BACK_EDGE + DEPTH / 2)

  const positions = geometry.attributes.position
  for (let index = 0; index < positions.count; index++) {
    positions.setY(index, hillHeight(positions.getX(index), positions.getZ(index)))
  }
  positions.needsUpdate = true

  // "Basic" material = a flat color that ignores lights.
  const material = new MeshBasicMaterial({ color: '#16260f' })

  return {
    object: new Mesh(geometry, material),
    dispose() {
      geometry.dispose()
      material.dispose()
    },
  }
}
