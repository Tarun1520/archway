import { BoxGeometry, CatmullRomCurve3, CylinderGeometry, Group, Mesh, SphereGeometry, TubeGeometry, Vector3 } from 'three'
import type { BufferGeometry, Material } from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import type { ScenePart } from '../scenePart'
import { CHAIR } from '../sceneSettings'
import { createChromeMaterial, createLeatherMaterial, createPlasticMaterial, disposeMaterial } from './materials'

/** How far the backrest leans back from upright, in radians (about 11 degrees). */
const BACK_LEAN = 0.2

/**
 * The office chair: leather cushions on a chrome frame, with a five-legged
 * base on casters.
 *
 * Inside this file the chair is built facing +z (the direction a person
 * sitting in it would look), standing on the ground at y = 0. At the end the
 * whole chair is moved and turned to its place beside the desk.
 */
export function createChair(): ScenePart {
  const chair = new Group()
  const geometries: BufferGeometry[] = []

  const chrome = createChromeMaterial()
  const leather = createLeatherMaterial()
  const plastic = createPlasticMaterial()

  /** Adds one piece to `parent` and remembers its geometry for clean-up. */
  const place = (parent: Group, geometry: BufferGeometry, material: Material, x: number, y: number, z: number) => {
    const mesh = new Mesh(geometry, material)
    mesh.position.set(x, y, z)
    mesh.castShadow = true
    mesh.receiveShadow = true
    parent.add(mesh)
    geometries.push(geometry)
    return mesh
  }

  // --- Base: five legs spreading out like a star, a caster under each ------
  for (let leg = 0; leg < 5; leg++) {
    // Each leg lives in its own group, turned a fifth of a circle further round.
    const spoke = new Group()
    spoke.rotation.y = (leg / 5) * Math.PI * 2
    chair.add(spoke)

    const legMesh = place(spoke, new BoxGeometry(0.045, 0.022, 0.3), chrome, 0, 0.085, 0.17)
    legMesh.rotation.x = 0.1 // slopes down slightly toward its caster
    place(spoke, new SphereGeometry(0.032, 16, 12), plastic, 0, 0.032, 0.31)
  }

  // --- Column: the gas lift between the base and the seat ------------------
  place(chair, new CylinderGeometry(0.036, 0.042, 0.16, 24), plastic, 0, 0.17, 0)
  place(chair, new CylinderGeometry(0.024, 0.024, 0.2, 24), chrome, 0, 0.33, 0)
  place(chair, new BoxGeometry(0.2, 0.03, 0.22), plastic, 0, 0.42, 0)

  // --- Seat ----------------------------------------------------------------
  place(chair, new RoundedBoxGeometry(0.5, 0.085, 0.48, 6, 0.04), leather, 0, 0.475, 0.02)

  // --- Backrest: three stacked pads, leaning back together -----------------
  // The pads sit in a group hinged at the back of the seat. Rotating the
  // group leans all three at once.
  const backrest = new Group()
  backrest.position.set(0, 0.5, -0.215)
  backrest.rotation.x = -BACK_LEAN
  chair.add(backrest)

  for (let pad = 0; pad < 3; pad++) {
    place(backrest, new RoundedBoxGeometry(0.48, 0.165, 0.075, 6, 0.035), leather, 0, 0.11 + pad * 0.175, 0)
  }
  // Chrome rails down both edges of the backrest hold the pads together.
  for (const side of [-1, 1]) {
    place(backrest, new BoxGeometry(0.012, 0.52, 0.03), chrome, side * 0.247, 0.285, -0.01)
  }

  // --- Arms: a chrome tube bent into a loop on each side -------------------
  for (const side of [-1, 1]) {
    // The tube follows a smooth curve through these points, front to back.
    const path = new CatmullRomCurve3([
      new Vector3(side * 0.255, 0.46, 0.2),
      new Vector3(side * 0.285, 0.6, 0.19),
      new Vector3(side * 0.29, 0.69, 0.08),
      new Vector3(side * 0.29, 0.69, -0.1),
      new Vector3(side * 0.265, 0.62, -0.23),
    ])
    place(chair, new TubeGeometry(path, 40, 0.011, 10), chrome, 0, 0, 0)
    // A padded rest on the flat top of the loop.
    place(chair, new RoundedBoxGeometry(0.045, 0.022, 0.2, 3, 0.01), plastic, side * 0.29, 0.705, -0.01)
    // A chrome rail along the edge of the seat.
    place(chair, new BoxGeometry(0.012, 0.03, 0.46), chrome, side * 0.255, 0.46, 0.02)
  }

  chair.position.set(CHAIR.position.x, 0, CHAIR.position.z)
  chair.rotation.y = CHAIR.rotationY

  return {
    object: chair,
    dispose() {
      for (const geometry of geometries) {
        geometry.dispose()
      }
      disposeMaterial(chrome)
      disposeMaterial(leather)
      disposeMaterial(plastic)
    },
  }
}
