import {
  CapsuleGeometry,
  Color,
  CylinderGeometry,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  Object3D,
  SphereGeometry,
  TorusGeometry,
} from 'three'
import type { BufferGeometry, Material } from 'three'
import { createCodeScreen, type CodeScreen } from './codeScreen'

/**
 * One agent robot, built from simple shapes (no model file to download):
 * a glossy white body with dark joints, a big rounded helmet with a black
 * visor and two glowing blue eyes, ear discs with blue rings and glowing
 * soles. About one unit tall, standing on y = 0, facing +z.
 *
 * Every moving part hangs from its own pivot (shoulders, elbows, hips, knees,
 * head), so the stage can make it walk, look around and reach out by turning
 * those pivots.
 */

export interface Limb {
  /** The upper joint (shoulder or hip). Turning it swings the whole limb. */
  upper: Group
  /** The lower joint (elbow or knee). */
  lower: Group
}

/** Height of the hip pivot: the body bows and sways around this point. */
export const HIP = 0.29

/** How one robot looks apart from the shared shapes. */
export interface RobotLook {
  /** The shell material (white for most, a colour for the lead). */
  shell?: MeshPhysicalMaterial
  /** The colour of the eyes and glowing rings. */
  glow?: string
}

export interface RobotRig {
  root: Group
  /** Everything above the legs, pivoting at the hips (y = HIP): bobs, sways and bows. */
  body: Group
  head: Group
  leftArm: Limb
  rightArm: Limb
  leftLeg: Limb
  rightLeg: Limb
  /** The right hand: where a cable's plug is held. */
  hand: Object3D
  /** The two ear rings (left, right): where another robot's cable plugs in. */
  ports: [Object3D, Object3D]
  eyes: Mesh[]
  /** The glowing parts' colour; brightened while the agent works. */
  glow: MeshBasicMaterial
  /** The visor as a screen of running code: a layer over the visor, shown only while the agent works. */
  codeLayer: Mesh
  /** Paints and moves the code on that layer. */
  code: CodeScreen
  dispose(): void
}

const EYE_BLUE = new Color('#4fb6ff')

/** Shared look, so all seven robots use the same few materials (cheaper to draw). */
export interface RobotMaterials {
  shell: MeshPhysicalMaterial
  joint: MeshStandardMaterial
  visor: MeshPhysicalMaterial
}

export function createRobotMaterials(): RobotMaterials {
  return {
    shell: new MeshPhysicalMaterial({ color: '#f1f2f4', roughness: 0.32, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.12 }),
    joint: new MeshStandardMaterial({ color: '#1c1d21', roughness: 0.45, metalness: 0.35 }),
    visor: new MeshPhysicalMaterial({ color: '#040507', roughness: 0.06, metalness: 0.25, clearcoat: 1, clearcoatRoughness: 0.04 }),
  }
}

export function buildRobot(materials: RobotMaterials, look: RobotLook = {}): RobotRig {
  const owned: (BufferGeometry | Material)[] = []
  const mesh = (geometry: BufferGeometry, material: Material) => {
    owned.push(geometry)
    const part = new Mesh(geometry, material)
    part.castShadow = false
    return part
  }

  // Each robot has its own glow, so one can light up while the others rest.
  const glowColour = look.glow ? new Color(look.glow) : EYE_BLUE.clone()
  const glow = new MeshBasicMaterial({ color: glowColour, toneMapped: false })
  owned.push(glow)
  const { joint, visor } = materials
  const shell = look.shell ?? materials.shell

  const root = new Group()
  // The body pivots at the hips; its parts are placed in an inner group
  // shifted back down, so their heights below still read as heights above the floor.
  const body = new Group()
  body.position.y = HIP
  root.add(body)
  const upperBody = new Group()
  upperBody.position.y = -HIP
  body.add(upperBody)

  // --- Torso ----------------------------------------------------------------
  const chest = mesh(new CapsuleGeometry(0.13, 0.07, 6, 18), shell)
  chest.scale.set(1.24, 0.96, 0.95)
  chest.position.y = 0.45
  upperBody.add(chest)

  const collar = mesh(new TorusGeometry(0.075, 0.012, 8, 28), glow)
  collar.rotation.x = Math.PI / 2
  collar.position.y = 0.555
  upperBody.add(collar)

  const waist = mesh(new CylinderGeometry(0.1, 0.105, 0.045, 24), joint)
  waist.position.y = 0.325
  upperBody.add(waist)

  const hips = mesh(new SphereGeometry(1, 20, 14), shell)
  hips.scale.set(0.14, 0.07, 0.11)
  hips.position.y = 0.285
  upperBody.add(hips)

  // --- Head -----------------------------------------------------------------
  const head = new Group()
  head.position.y = 0.6
  upperBody.add(head)

  const neck = mesh(new CylinderGeometry(0.045, 0.055, 0.06, 16), joint)
  neck.position.y = -0.03
  head.add(neck)

  const helmet = mesh(new SphereGeometry(0.235, 32, 24), shell)
  helmet.scale.set(1.05, 0.93, 0.95)
  helmet.position.y = 0.2
  head.add(helmet)

  // The visor: a slice of a slightly bigger sphere, facing forward.
  const visorWidth = 1.95
  const face = mesh(new SphereGeometry(0.236, 32, 20, Math.PI / 2 - visorWidth / 2, visorWidth, Math.PI * 0.3, Math.PI * 0.4), visor)
  face.scale.set(1.06, 0.95, 0.97)
  face.position.y = 0.2
  head.add(face)

  // The same slice of visor again, a hair outside, carrying the running code.
  const code = createCodeScreen(`#${glowColour.getHexString()}`, owned.length * 0.37 + glowColour.r)
  const codeMaterial = new MeshBasicMaterial({ map: code.texture, toneMapped: false })
  owned.push(codeMaterial)
  const codeLayer = mesh(new SphereGeometry(0.2375, 32, 20, Math.PI / 2 - visorWidth / 2, visorWidth, Math.PI * 0.3, Math.PI * 0.4), codeMaterial)
  codeLayer.scale.set(1.06, 0.95, 0.97)
  codeLayer.position.y = 0.2
  codeLayer.visible = false
  head.add(codeLayer)

  const eyes = [-1, 1].map((side) => {
    const eye = mesh(new SphereGeometry(0.047, 16, 12), glow)
    eye.scale.set(1, 1, 0.35)
    eye.position.set(side * 0.085, 0.19, 0.222)
    head.add(eye)
    return eye
  })

  const ports: Object3D[] = []
  for (const side of [-1, 1]) {
    const ear = mesh(new CylinderGeometry(0.07, 0.07, 0.05, 24), shell)
    ear.rotation.z = Math.PI / 2
    ear.position.set(side * 0.245, 0.2, 0)
    head.add(ear)
    const ring = mesh(new TorusGeometry(0.052, 0.009, 8, 28), glow)
    ring.rotation.y = Math.PI / 2
    ring.position.set(side * 0.272, 0.2, 0)
    head.add(ring)
    ports.push(ring)
  }

  // --- Arms -----------------------------------------------------------------
  const arm = (side: number): Limb & { hand: Object3D } => {
    const upper = new Group()
    upper.position.set(side * 0.205, 0.505, 0)
    upperBody.add(upper)
    const shoulder = mesh(new SphereGeometry(0.052, 16, 12), shell)
    upper.add(shoulder)
    const upperArm = mesh(new CapsuleGeometry(0.046, 0.075, 4, 12), shell)
    upperArm.position.y = -0.08
    upper.add(upperArm)

    const lower = new Group()
    lower.position.y = -0.16
    upper.add(lower)
    const elbow = mesh(new SphereGeometry(0.032, 12, 10), joint)
    lower.add(elbow)
    const forearm = mesh(new CapsuleGeometry(0.044, 0.065, 4, 12), shell)
    forearm.position.y = -0.07
    lower.add(forearm)
    const hand = mesh(new SphereGeometry(0.04, 12, 10), joint)
    hand.scale.set(1, 1.15, 0.8)
    hand.position.y = -0.145
    lower.add(hand)

    // Arms hang slightly away from the body, like the reference.
    upper.rotation.z = side * 0.12
    return { upper, lower, hand }
  }
  const leftArm = arm(-1)
  const rightArm = arm(1)

  // --- Legs -----------------------------------------------------------------
  const leg = (side: number): Limb => {
    const upper = new Group()
    upper.position.set(side * 0.078, 0.255, 0)
    root.add(upper)
    const thigh = mesh(new CapsuleGeometry(0.044, 0.045, 4, 12), joint)
    thigh.position.y = -0.055
    upper.add(thigh)

    const lower = new Group()
    lower.position.y = -0.12
    upper.add(lower)
    const shin = mesh(new CapsuleGeometry(0.058, 0.04, 4, 14), shell)
    shin.position.y = -0.045
    lower.add(shin)
    const boot = mesh(new SphereGeometry(1, 18, 12), shell)
    boot.scale.set(0.072, 0.048, 0.098)
    boot.position.set(0, -0.1, 0.018)
    lower.add(boot)
    const sole = mesh(new TorusGeometry(0.064, 0.009, 6, 24), glow)
    sole.rotation.x = Math.PI / 2
    sole.scale.set(1, 1.45, 1)
    sole.position.set(0, -0.128, 0.018)
    lower.add(sole)
    return { upper, lower }
  }
  const leftLeg = leg(-1)
  const rightLeg = leg(1)

  return {
    root,
    body,
    head,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    hand: rightArm.hand,
    ports: [ports[0], ports[1]],
    eyes,
    glow,
    codeLayer,
    code,
    dispose() {
      code.dispose()
      for (const item of owned) item.dispose()
    },
  }
}
