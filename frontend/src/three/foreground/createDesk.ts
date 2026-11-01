import { BoxGeometry, Group, Mesh } from 'three'
import type { BufferGeometry, Material } from 'three'
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js'
import type { ScenePart } from '../scenePart'
import { DESK } from '../sceneSettings'
import { createPlasticMaterial, createSteelMaterial, createWoodMaterial, disposeMaterial } from './materials'

/** Thickness of the steel tube the frame is made of. */
const TUBE = 0.035

/** The drawer unit hanging under the right side of the desk. */
const DRAWERS = { width: 0.42, height: 0.44, depth: 0.54, centerX: 0.42, centerZ: 0.06 }

/**
 * The desk: a pale oak top on a black steel frame, with a two-drawer unit
 * under the right side.
 *
 * It is built the way a child builds with blocks: every piece is a box of a
 * certain size, moved to the right place. The `place` helper below does that
 * and remembers each piece so it can be cleaned up later.
 */
export function createDesk(): ScenePart {
  const group = new Group()
  const geometries: BufferGeometry[] = []

  const oak = createWoodMaterial('#b98c5a')
  const paleOak = createWoodMaterial('#c79f6e')
  const steel = createSteelMaterial()
  const plastic = createPlasticMaterial()

  /** Adds one piece to the desk at the given center position. */
  const place = (geometry: BufferGeometry, material: Material, x: number, y: number, z: number) => {
    const mesh = new Mesh(geometry, material)
    mesh.position.set(x, y, z)
    mesh.castShadow = true // it blocks sunlight
    mesh.receiveShadow = true // shadows from other pieces can fall on it
    group.add(mesh)
    geometries.push(geometry)
    return mesh
  }

  // --- The top -------------------------------------------------------------
  // A rounded box: a box with softened edges, which catch the light.
  const topCenterY = DESK.topHeight - DESK.topThickness / 2
  place(new RoundedBoxGeometry(DESK.width, DESK.topThickness, DESK.depth, 3, 0.006), oak, 0, topCenterY, 0)

  // --- The frame -----------------------------------------------------------
  const legHeight = DESK.topHeight - DESK.topThickness
  const legX = DESK.width / 2 - 0.04
  const legZ = DESK.depth / 2 - 0.04

  // Four legs, one at each corner. The loops visit (-1, -1), (-1, 1), (1, -1), (1, 1).
  for (const sideX of [-1, 1]) {
    for (const sideZ of [-1, 1]) {
      place(new BoxGeometry(TUBE, legHeight, TUBE), steel, sideX * legX, legHeight / 2, sideZ * legZ)
    }
  }

  // Rails under the top that join the legs: one at the front, back, left and right.
  const railY = legHeight - TUBE / 2
  for (const sideZ of [-1, 1]) {
    place(new BoxGeometry(legX * 2, TUBE, TUBE), steel, 0, railY, sideZ * legZ)
  }
  for (const sideX of [-1, 1]) {
    place(new BoxGeometry(TUBE, TUBE, legZ * 2), steel, sideX * legX, railY, 0)
  }

  // --- The drawer unit -----------------------------------------------------
  const drawersTop = legHeight - TUBE
  const drawersCenterY = drawersTop - DRAWERS.height / 2
  place(
    new RoundedBoxGeometry(DRAWERS.width, DRAWERS.height, DRAWERS.depth, 3, 0.006),
    paleOak,
    DRAWERS.centerX,
    drawersCenterY,
    DRAWERS.centerZ,
  )

  // The front of the unit faces the viewer (+z). A thin dark line shows where
  // the two drawers meet, and each drawer has a slim handle.
  const frontZ = DRAWERS.centerZ + DRAWERS.depth / 2
  place(new BoxGeometry(DRAWERS.width - 0.03, 0.004, 0.004), plastic, DRAWERS.centerX, drawersCenterY, frontZ)
  for (const drawer of [-1, 1]) {
    const handleY = drawersCenterY + drawer * (DRAWERS.height / 4)
    place(new BoxGeometry(0.13, 0.012, 0.014), plastic, DRAWERS.centerX, handleY + 0.06, frontZ + 0.006)
  }

  return {
    object: group,
    dispose() {
      for (const geometry of geometries) {
        geometry.dispose()
      }
      disposeMaterial(oak)
      disposeMaterial(paleOak)
      disposeMaterial(steel)
      disposeMaterial(plastic)
    },
  }
}
