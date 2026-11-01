import {
  ACESFilmicToneMapping,
  CanvasTexture,
  CircleGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  HemisphereLight,
  type Light,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  Plane,
  MeshPhysicalMaterial,
  PMREMGenerator,
  Raycaster,
  Vector2,
  QuadraticBezierCurve3,
  RingGeometry,
  Scene,
  SphereGeometry,
  SRGBColorSpace,
  TubeGeometry,
  Vector3,
  WebGLRenderer,
} from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { AGENTS, type AgentId, type AgentStatus, type TeamPicture } from '../../../../lib/agentTeam'
import { buildRobot, createRobotMaterials, HIP, type RobotRig } from './buildRobot'
import { GREETINGS, type Pose } from './greetings'
import { ARRIVALS, DEPARTURES, type Act, type ActFrame } from './teamActs'
import { createGroundGlow, createJetpack, createSmoke, softTexture, type Jetpack } from './teamProps'

/** Three.js layers: what is drawn only inside the panel, and what may be drawn over the whole window. */
const GROUND_LAYER = 0
const AIR_LAYER = 1

/**
 * The 3D stage for the agents corner: seven robots on a round floor, driven by
 * the team picture from the run's real events (lib/agentTeam.ts).
 *
 *   working   the visor becomes a screen of scrolling code, the head looks around, the arms type
 *   idle      eyes dim, standing still, breathing
 *   done      eyes narrow into a contented look
 *   message   the sender WALKS to the recipient, raises its arm and PLUGS a
 *             cable into the recipient's ear port; a light pulse runs along the
 *             cable (the message), then it unplugs and walks back home.
 *             A message to the whole team sends a ring of light out instead.
 *   hello     pointing at a robot makes it greet you with a move of its own
 *             (greetings.ts); the wrapper shows what it says in a bubble.
 *   huddle    while the options are drafted, the specialists gather round the
 *             lead, facing it (setHuddle); they go back to their places after.
 *   enter     each robot comes onto the stage in its own way, with a prop
 *             (teamActs.ts, teamProps.ts): the lead on a jetpack, Laya on a
 *             hoverboard, the judge on a skateboard ...
 *   exit      and leaves it in its own way, just before the options appear.
 *
 * The canvas covers the WHOLE WINDOW (a layer the page cannot click through to:
 * it has no pointer events). The camera is set up so that the panel's
 * rectangle shows exactly what a panel-sized canvas would, and normally only
 * that rectangle is drawn (a scissor). While anything is in the air (a robot
 * coming on or going off, or its smoke still drifting), the robots and smoke
 * are drawn over the whole window instead, once, so they really arrive from
 * beyond the edge of the screen and leave it, with no box around them.
 *
 * The lead is drawn in the studio's vermilion with warm eyes, so it stands
 * out from the six white specialists.
 *
 * It is plain three.js, no React: the React wrapper (AgentStage3D.tsx) creates
 * it, feeds it the team picture and positions the name labels it reports.
 * It only draws frames while something moves, so a quiet team costs nothing.
 */

export interface TeamStage {
  update(team: TeamPicture): void
  /** Every robot comes onto the stage in its own way. */
  enter(): void
  /** Every robot leaves the stage in its own way; resolves once all are gone. */
  exit(): Promise<void>
  /** Gather round the lead (true), or go back to their own places (false). */
  setHuddle(on: boolean): void
  /** The pointer moved over the stage (CSS pixels inside the canvas), or left it (null). Returns the robot under it. */
  pointAt(x: number | null, y: number | null): AgentId | null
  /** Makes one robot say hello (also used when its name label is hovered). */
  greet(id: AgentId): void
  /**
   * Where the panel is in the window (CSS pixels), the part of it that can be seen (inside any scrolling box),
   * and the window's size. Called on resize and scroll.
   */
  place(panel: Rect, clip: Rect, viewWidth: number, viewHeight: number): void
  /** Takes every robot off the stage at once (before an entrance that waits for the page to be seen). */
  hide(): void
  /** Every robot on the stage greets at once, each with its own move (greetings.ts), without speech bubbles. */
  waveAll(): void
  setVisible(visible: boolean): void
  dispose(): void
}

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface TeamStageOptions {
  reducedMotion: boolean
  /** Where each robot's feet and head top are on screen, in CSS pixels, every drawn frame: for the HTML labels and speech bubbles. */
  onLabels: (positions: Record<AgentId, { x: number; y: number; headY: number; hidden: boolean }>) => void
  /** A robot started (id) or finished (null) its greeting: the wrapper shows its speech bubble. */
  onGreeting: (id: AgentId | null) => void
}

/** Where each robot stands on the floor (x to the right, z toward the viewer). */
const HOMES: Record<AgentId, [number, number]> = {
  lead: [0, 0.0],
  analyst: [-1.75, -0.3],
  scout: [-0.85, -1.3],
  judge: [0.85, -1.3],
  projects: [1.75, -0.3],
  reviewer: [-0.8, 1.05],
  decider: [0.8, 1.05],
}

/** Where each robot stands in the huddle round the lead (the lead keeps its place). */
const HUDDLE: Record<AgentId, [number, number]> = {
  lead: [0, 0.0],
  analyst: [-0.95, 0.05],
  scout: [-0.62, -0.6],
  judge: [0.62, -0.6],
  projects: [0.95, 0.05],
  reviewer: [-0.9, 0.78],
  decider: [0.9, 0.78],
}

/**
 * Robots whose name is shown ABOVE their head rather than under their feet:
 * the back row, whose feet the front robots stand in front of.
 */
export const NAME_ABOVE: ReadonlySet<AgentId> = new Set<AgentId>(['analyst', 'scout', 'judge', 'projects'])

/** Robots are drawn a bit smaller than one unit, so they have room to walk around each other. */
const ROBOT_SCALE = 1.0
const LEAD_SCALE = 1.12

const CAMERA = new Vector3(0, 2.35, 4.4)
const LOOK_AT = new Vector3(0, 0.1, -0.08)
const LEAD_GLOW = new Color('#ffbf7a')
const WALK_SPEED = 0.95 // floor units per second
const STOP_DISTANCE = 0.5 // how far beside the recipient the sender stands
const BLUE = new Color('#4fb6ff')

// How long each part of a delivery takes, in seconds.
const REACH = 0.35
const PLUG = 0.45
const TALK = 1.6
const UNPLUG = 0.35

type DeliveryPhase = 'walk-out' | 'reach' | 'plug' | 'talk' | 'unplug' | 'lower' | 'walk-back'

interface Delivery {
  from: AgentId
  to: AgentId
  phase: DeliveryPhase
  time: number
  stop: Vector3
}

interface ActiveMove {
  kind: 'enter' | 'exit'
  act: Act
  time: number
  started: boolean
}

interface Actor {
  id: AgentId
  rig: RobotRig
  home: Vector3
  /** Where it stands now: its home, or its place in the huddle. */
  station: Vector3
  /** Which way it faces when standing at its station. */
  faceYaw: number
  /** Coming onto the stage, or leaving it (teamActs.ts), or null. */
  move: ActiveMove | null
  /** Off the stage (after leaving). */
  gone: boolean
  /** The jetpack it flies in and out on. */
  prop: Jetpack
  /** The warm light its jet throws on the floor when low. */
  floorGlow: ReturnType<typeof createGroundGlow>
  scale: number
  /** Facing the viewer when at home. */
  homeYaw: number
  yaw: number
  targetYaw: number
  status: AgentStatus
  /** Where it is walking to, or null when standing. */
  walkTo: Vector3 | null
  stride: number
  /** How bright the eyes are, eased toward the status's level. */
  light: number
  /** How far the right arm is raised toward a partner (0 down, 1 reaching). */
  reach: number
  /** Extra glow while a cable is plugged into this robot's port. */
  flash: number
  /** Where the head turns while someone stands beside it (null = its own look). */
  headTurn: number | null
  /** The colour of its eyes and rings at full strength. */
  glowBase: Color
  /** A greeting in progress: seconds since it began, or null. */
  greeting: number | null
  /** When it may greet again (so a twitchy pointer does not restart it). */
  greetAgain: number
  nextBlink: number
  blink: number
  offset: number
  shadow: Mesh
}

const LIGHT: Record<AgentStatus, number> = { working: 1.25, idle: 0.38, done: 0.62 }

function softDiscTexture(inner: string, outer: string): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 128
  const context = canvas.getContext('2d')!
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64)
  gradient.addColorStop(0, inner)
  gradient.addColorStop(1, outer)
  context.fillStyle = gradient
  context.fillRect(0, 0, 128, 128)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  return texture
}

export function createTeamStage(canvas: HTMLCanvasElement, options: TeamStageOptions): TeamStage {
  // Throws when WebGL is not available; the wrapper then shows the flat robots instead.
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.autoClear = false // each frame clears the whole layer, then draws the panel, then (while moving) the robots anywhere
  let panel: Rect = { x: 0, y: 0, width: 300, height: 200 }
  let clip: Rect = panel
  let view = { width: 300, height: 200 }
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.outputColorSpace = SRGBColorSpace
  // Nothing is drawn below the floor: a robot rising through it (or sinking into it) appears to come out of a hole.
  renderer.clippingPlanes = [new Plane(new Vector3(0, 1, 0), 0.01)]

  const scene = new Scene()
  const camera = new PerspectiveCamera(32, 1.4, 0.1, 40)
  camera.position.copy(CAMERA)
  camera.lookAt(LOOK_AT)

  // Soft studio reflections for the glossy shells, plus a key light and a cool rim light.
  const environmentMaker = new PMREMGenerator(renderer)
  const environment = environmentMaker.fromScene(new RoomEnvironment(), 0.04).texture
  scene.environment = environment
  scene.environmentIntensity = 0.55
  scene.add(new HemisphereLight('#ffffff', '#202020', 0.55))
  const key = new DirectionalLight('#ffffff', 2.1)
  key.position.set(2.5, 5, 4)
  scene.add(key)
  const rim = new DirectionalLight('#8fc8ff', 1.3)
  rim.position.set(-3, 2.5, -4)
  scene.add(rim)

  // --- The floor: a soft round pool of light, and a faint accent ring under the lead ---
  const disposables: { dispose(): void }[] = [renderer, environment, environmentMaker]
  const floorTexture = softDiscTexture('rgba(46,46,46,0.95)', 'rgba(15,15,15,0)')
  const floorGeometry = new CircleGeometry(2.6, 64)
  const floorMaterial = new MeshBasicMaterial({ map: floorTexture, transparent: true, depthWrite: false })
  const floor = new Mesh(floorGeometry, floorMaterial)
  floor.rotation.x = -Math.PI / 2
  floor.scale.set(1, 0.8, 1)
  scene.add(floor)
  const ringGeometry = new RingGeometry(0.34, 0.352, 64)
  const ringMaterial = new MeshBasicMaterial({ color: '#ff3d00', transparent: true, opacity: 0.45, depthWrite: false })
  const leadRing = new Mesh(ringGeometry, ringMaterial)
  leadRing.rotation.x = -Math.PI / 2
  leadRing.position.set(HOMES.lead[0], 0.002, HOMES.lead[1])
  scene.add(leadRing)
  disposables.push(floorTexture, floorGeometry, floorMaterial, ringGeometry, ringMaterial)

  // --- The robots ------------------------------------------------------------------
  const materials = createRobotMaterials()
  disposables.push(materials.shell, materials.joint, materials.visor)
  const shadowTexture = softDiscTexture('rgba(0,0,0,0.55)', 'rgba(0,0,0,0)')
  const shadowGeometry = new CircleGeometry(0.24, 32)
  const shadowMaterial = new MeshBasicMaterial({ map: shadowTexture, transparent: true, depthWrite: false })
  disposables.push(shadowTexture, shadowGeometry, shadowMaterial)

  const leadShell = new MeshPhysicalMaterial({ color: '#ff4a14', roughness: 0.3, metalness: 0.05, clearcoat: 1, clearcoatRoughness: 0.1 })
  disposables.push(leadShell)

  const puffTexture = softTexture() // shared by the smoke, the nozzle glows and the light on the floor
  disposables.push(puffTexture)
  const actors = {} as Record<AgentId, Actor>
  const owner = new Map<number, AgentId>() // mesh id -> robot, for finding what the pointer is on
  AGENTS.forEach((agent, index) => {
    const rig = buildRobot(materials, agent.id === 'lead' ? { shell: leadShell, glow: LEAD_GLOW.getStyle() } : {})
    rig.root.traverse((part) => owner.set(part.id, agent.id))
    const [x, z] = HOMES[agent.id]
    const home = new Vector3(x, 0, z)
    rig.root.position.copy(home)
    rig.root.scale.setScalar(agent.id === 'lead' ? LEAD_SCALE : ROBOT_SCALE)
    const homeYaw = Math.atan2(CAMERA.x - x, CAMERA.z - z) * 0.8
    rig.root.rotation.y = homeYaw
    scene.add(rig.root)
    const shadow = new Mesh(shadowGeometry, shadowMaterial.clone()) // its own copy: it fades on its own while the robot flies
    shadow.rotation.x = -Math.PI / 2
    shadow.position.set(x, 0.003, z)
    scene.add(shadow)
    actors[agent.id] = {
      id: agent.id, rig, home, station: home.clone(), faceYaw: homeYaw, move: null, gone: false,
      prop: createJetpack(rig, agent.id === 'lead' ? LEAD_GLOW : BLUE, puffTexture),
      floorGlow: createGroundGlow(puffTexture),
      scale: agent.id === 'lead' ? LEAD_SCALE : ROBOT_SCALE, homeYaw, yaw: homeYaw, targetYaw: homeYaw, status: 'idle', walkTo: null, stride: 0,
      light: LIGHT.idle, reach: 0, flash: 0, headTurn: null, glowBase: agent.id === 'lead' ? LEAD_GLOW : BLUE, greeting: null, greetAgain: 0, nextBlink: 1.5 + index * 0.7, blink: 0, offset: index * 1.3, shadow,
    }
  })

  // The "air" layer: the robots (with their packs) and the smoke. While anything is in the air it is drawn over the
  // whole window; the rest (floor, shadows, rings) only inside the panel (renderFrame). Lights must light both.
  for (const actor of Object.values(actors)) actor.rig.root.traverse((part) => part.layers.set(AIR_LAYER))
  scene.traverse((part) => {
    if ((part as Light).isLight) part.layers.enableAll()
  })

  // --- Cable, plug and pulse (one delivery at a time) ---------------------------------
  const cableMaterial = new MeshBasicMaterial({ color: BLUE.clone().multiplyScalar(0.9), toneMapped: false })
  const plugGeometry = new CylinderGeometry(0.022, 0.022, 0.065, 12)
  const plugMaterial = new MeshBasicMaterial({ color: '#d9e3ec' })
  const plug = new Mesh(plugGeometry, plugMaterial)
  plug.visible = false
  scene.add(plug)
  const pulseGeometry = new SphereGeometry(0.03, 12, 10)
  const pulseMaterial = new MeshBasicMaterial({ color: '#ffffff', toneMapped: false })
  const pulse = new Mesh(pulseGeometry, pulseMaterial)
  pulse.visible = false
  scene.add(pulse)
  disposables.push(cableMaterial, plugGeometry, plugMaterial, pulseGeometry, pulseMaterial)
  let cable: Mesh | null = null
  let curve: QuadraticBezierCurve3 | null = null
  const CABLE_SEGMENTS = 40
  const CABLE_SIDES = 6

  const removeCable = () => {
    if (cable) {
      scene.remove(cable)
      cable.geometry.dispose()
      cable = null
    }
    curve = null
    plug.visible = false
    pulse.visible = false
  }

  /** A cable from the sender's hand to the recipient's ear port, sagging a little in the middle. */
  const layCable = (from: Actor, to: Actor) => {
    removeCable()
    scene.updateMatrixWorld()
    const start = from.rig.hand.getWorldPosition(new Vector3())
    const ears = to.rig.ports.map((ear) => ear.getWorldPosition(new Vector3()))
    const end = ears[0].distanceTo(start) < ears[1].distanceTo(start) ? ears[0] : ears[1]
    const middle = start.clone().lerp(end, 0.5)
    middle.y -= 0.14
    curve = new QuadraticBezierCurve3(start, middle, end)
    cable = new Mesh(new TubeGeometry(curve, CABLE_SEGMENTS, 0.014, CABLE_SIDES, false), cableMaterial)
    scene.add(cable)
  }

  /** Shows the first `share` (0..1) of the cable, with the plug at its tip. */
  const showCable = (share: number) => {
    if (!cable || !curve) return
    const segments = Math.round(CABLE_SEGMENTS * share)
    cable.geometry.setDrawRange(0, segments * CABLE_SIDES * 6) // six indices per side per segment
    plug.visible = share > 0.02
    const at = Math.max(0.001, Math.min(share, 1))
    plug.position.copy(curve.getPointAt(at))
    plug.quaternion.setFromUnitVectors(new Vector3(0, 1, 0), curve.getTangentAt(at).normalize())
  }

  // --- Rings of light, for messages to the whole team ---------------------------------
  const rippleGeometry = new RingGeometry(0.9, 1, 64)
  disposables.push(rippleGeometry)
  const ripples: { mesh: Mesh; age: number }[] = []
  const sendRipple = (from: Actor) => {
    const material = new MeshBasicMaterial({ color: BLUE, transparent: true, opacity: 0.6, depthWrite: false, toneMapped: false })
    const mesh = new Mesh(rippleGeometry, material)
    mesh.rotation.x = -Math.PI / 2
    mesh.position.set(from.rig.root.position.x, 0.004, from.rig.root.position.z)
    scene.add(mesh)
    ripples.push({ mesh, age: 0 })
  }

  // --- Exhaust from the jetpack -----------------------------------------------------------------
  const smoke = createSmoke(scene, puffTexture)
  smoke.mesh.layers.set(AIR_LAYER)
  for (const actor of Object.values(actors)) scene.add(actor.floorGlow.mesh)

  // --- State ------------------------------------------------------------------------------
  const seenMessages = new Set<string>()
  let firstUpdate = true
  const queue: { from: AgentId; to: AgentId }[] = []
  let delivery: Delivery | null = null
  let staticCableUntil = 0 // reduced motion: the cable simply appears for a moment
  let live = false
  let visible = true
  let leaving: (() => void) | null = null // resolves exit() once every robot is gone
  let wakeUntil = 0
  let elapsed = 0
  let frame = 0
  let last = 0
  let stepDt = 1 / 60 // the smoothed step of the real clock (draw)

  const wake = (seconds = 1.5) => {
    wakeUntil = Math.max(wakeUntil, elapsed + seconds)
    start()
  }

  const begin = (from: AgentId, to: AgentId) => {
    const sender = actors[from]
    const receiver = actors[to]
    if (options.reducedMotion) {
      layCable(sender, receiver)
      showCable(1)
      staticCableUntil = elapsed + 2.4
      wake(2.6)
      return
    }
    // The sender stops BESIDE the recipient (on its own side), so the viewer
    // sees both robots in profile with the cable between them.
    if (sender.gone || receiver.gone || sender.move || receiver.move) return // not on stage: no cable
    const side = Math.sign(sender.station.x - receiver.station.x) || 1
    const stop = receiver.station.clone().add(new Vector3(side * STOP_DISTANCE, 0, 0.06))
    delivery = { from, to, phase: 'walk-out', time: 0, stop }
    sender.walkTo = stop
  }

  // --- One frame ------------------------------------------------------------------------
  const ease = (from: number, to: number, rate: number, dt: number) => from + (to - from) * Math.min(1, dt * rate)
  const turnToward = (actor: Actor, point: Vector3) => {
    const position = actor.rig.root.position
    actor.targetYaw = Math.atan2(point.x - position.x, point.z - position.z)
  }

  const stepDelivery = (dt: number) => {
    if (!delivery) {
      const next = queue.shift()
      if (next) begin(next.from, next.to)
      return
    }
    const sender = actors[delivery.from]
    const receiver = actors[delivery.to]
    delivery.time += dt
    switch (delivery.phase) {
      case 'walk-out':
        receiver.headTurn = Math.sign(sender.rig.root.position.x - receiver.rig.root.position.x) * 0.55
        if (!sender.walkTo) {
          delivery.phase = 'reach'
          delivery.time = 0
          turnToward(sender, receiver.rig.root.position)
        }
        break
      case 'reach':
        sender.reach = Math.min(1, delivery.time / REACH)
        if (delivery.time >= REACH) {
          layCable(sender, receiver)
          showCable(0)
          delivery.phase = 'plug'
          delivery.time = 0
        }
        break
      case 'plug':
        showCable(Math.min(1, delivery.time / PLUG))
        if (delivery.time >= PLUG) {
          delivery.phase = 'talk'
          delivery.time = 0
        }
        break
      case 'talk': {
        receiver.flash = 1
        const along = (delivery.time * 1.25) % 1
        if (curve) {
          pulse.visible = true
          pulse.position.copy(curve.getPointAt(along))
        }
        if (delivery.time >= TALK) {
          pulse.visible = false
          delivery.phase = 'unplug'
          delivery.time = 0
        }
        break
      }
      case 'unplug':
        showCable(1 - Math.min(1, delivery.time / UNPLUG))
        if (delivery.time >= UNPLUG) {
          removeCable()
          delivery.phase = 'lower'
          delivery.time = 0
        }
        break
      case 'lower':
        sender.reach = 1 - Math.min(1, delivery.time / REACH)
        if (delivery.time >= REACH) {
          receiver.headTurn = null
          sender.walkTo = sender.station.clone()
          delivery.phase = 'walk-back'
          delivery.time = 0
        }
        break
      case 'walk-back':
        if (!sender.walkTo) {
          sender.targetYaw = sender.faceYaw
          delivery = null
        }
        break
    }
  }

  /** The eyes (brightness, blinks, a smile when done) and the visor's code screen while the agent works. */
  const stepEyes = (actor: Actor, dt: number, time: number) => {
    const { rig } = actor
    const still = options.reducedMotion
    const working = actor.status === 'working'
    // The eyes: brightness by status, a short blink now and then, narrowed when done.
    actor.light = ease(actor.light, LIGHT[actor.status], 5, dt)
    actor.flash = Math.max(0, actor.flash - dt * 2.5)
    const greetingGlow = actor.greeting !== null ? 0.5 : 0
    rig.glow.color.copy(actor.glowBase).multiplyScalar(actor.light + actor.flash * 0.9 + greetingGlow)
    if (!still && time > actor.nextBlink) {
      actor.blink = 0.14
      actor.nextBlink = time + 3 + ((actor.offset * 7.3) % 3)
    }
    actor.blink = Math.max(0, actor.blink - dt)
    const open = actor.status === 'done' || actor.greeting !== null ? 0.32 : 1 // narrowed = smiling
    for (const eye of rig.eyes) eye.scale.y = ease(eye.scale.y, actor.blink > 0 ? 0.12 : open, 30, dt)

    // The visor turns into a screen of running code while this agent works, and
    // back into eyes when it stops. (Reduced motion: one still frame of code.)
    if (working !== rig.codeLayer.visible) {
      rig.codeLayer.visible = working
      for (const eye of rig.eyes) eye.visible = !working
      if (working && still) rig.code.still()
    }
    if (working && !still) rig.code.tick(time)
    }

  /**
   * Places and poses a robot from one frame of its flight act, and drives its jetpack: flames, exhaust that trails
   * behind it, dust where the jet hits the floor, a burst at touchdown and lift-off, and warm light on the floor.
   */
  const centre = new Vector3()
  const turned = new Vector3()
  const carry = new Vector3()
  const applyAct = (actor: Actor, frame: ActFrame, dt: number, time: number) => {
    const { rig } = actor
    const limbs = frame.limbs
    actor.yaw = actor.targetYaw = frame.yaw ?? actor.faceYaw
    // The whole body tilts with the thrust, about its middle (not about its feet), as a flyer does.
    rig.root.rotation.order = 'YXZ'
    rig.root.rotation.set(frame.pitch, actor.yaw, frame.roll)
    rig.root.scale.setScalar(actor.scale)
    centre.set(0, 0.45 * actor.scale, 0)
    turned.copy(centre).applyEuler(rig.root.rotation)
    rig.root.position.set(actor.station.x + frame.x, frame.lift, actor.station.z + frame.z).add(centre).sub(turned)
    rig.body.position.y = HIP
    rig.body.rotation.x = frame.lean
    rig.body.rotation.z = 0
    rig.leftLeg.upper.rotation.x = limbs.lLeg ?? 0
    rig.rightLeg.upper.rotation.x = limbs.rLeg ?? 0
    rig.leftLeg.upper.rotation.z = limbs.lLegOut ?? 0
    rig.rightLeg.upper.rotation.z = limbs.rLegOut ?? 0
    rig.leftLeg.lower.rotation.x = limbs.lKnee ?? 0
    rig.rightLeg.lower.rotation.x = limbs.rKnee ?? 0
    rig.leftArm.upper.rotation.x = limbs.lArm ?? 0
    rig.rightArm.upper.rotation.x = limbs.rArm ?? 0
    rig.leftArm.upper.rotation.z = limbs.lArmOut ?? -0.12
    rig.rightArm.upper.rotation.z = limbs.rArmOut ?? 0.12
    rig.leftArm.lower.rotation.x = limbs.lElbow ?? -0.12
    rig.rightArm.lower.rotation.x = limbs.rElbow ?? -0.12
    rig.leftArm.lower.rotation.z = 0
    rig.rightArm.lower.rotation.z = 0
    rig.head.rotation.x = limbs.headX ?? 0
    rig.head.rotation.y = limbs.headY ?? 0
    rig.head.rotation.z = 0
    // The shadow stays on the floor, spreading and fading as the robot rises.
    const floorX = actor.station.x + frame.x
    const floorZ = actor.station.z + frame.z
    const height = Math.max(0, frame.lift)
    actor.shadow.position.set(floorX, 0.003, floorZ)
    actor.shadow.scale.setScalar(1 + height * 0.3)
    ;(actor.shadow.material as MeshBasicMaterial).opacity = Math.max(0, 1 - height * 0.45)

    actor.prop.update(frame.prop, dt, time)
    const thrust = frame.prop?.thrust ?? 0
    if (thrust > 0.04 && (frame.prop?.appear ?? 0) > 0.5) {
      rig.root.updateMatrixWorld(true)
      const { points, direction } = actor.prop.exhaust()
      carry.set(...frame.velocity)
      smoke.exhaust(points, direction, 1.6 + 1.8 * Math.min(1.6, thrust), 22 * Math.min(1.8, thrust), carry, dt)
      // The jet hitting the floor: dust rolls out in a ring, and the floor glows warm under it.
      const nozzleHeight = height + 0.3
      const near = Math.max(0, 1 - nozzleHeight / 1.6)
      if (near > 0) smoke.groundRing(floorX, floorZ, near * Math.min(1.4, thrust), dt)
      actor.floorGlow.set(floorX, floorZ, near * near * thrust * 0.9)
    } else {
      actor.floorGlow.set(floorX, floorZ, 0)
    }
    if (frame.burst) smoke.burst(floorX, floorZ, frame.burst)
  }

  const stepActor = (actor: Actor, dt: number, time: number, realDt: number) => {
    const { rig } = actor
    const still = options.reducedMotion

    // Coming on or going off (teamActs.ts): the act places and poses the whole robot, with its prop.
    if (actor.move) {
      const move = actor.move
      // Coming and going follow the real clock (a slow machine still gets the team on and off in time, in fewer steps).
      move.time += realDt
      const t = move.time - move.act.delay
      if (t >= 0 && !move.started) {
        move.started = true
        rig.root.visible = true
        actor.shadow.visible = true
      }
      if (t >= 0 || move.kind === 'enter') {
        if (t >= move.act.duration) {
          actor.move = null
          actor.prop.update(null, dt, time)
          actor.floorGlow.set(0, 0, 0)
          rig.root.rotation.set(0, actor.yaw, 0)
          if (move.kind === 'exit') {
            actor.gone = true
            rig.root.visible = false
            actor.shadow.visible = false
          } else {
            rig.root.position.copy(actor.station)
            actor.shadow.scale.setScalar(1)
            ;(actor.shadow.material as MeshBasicMaterial).opacity = 1
            actor.yaw = actor.targetYaw = actor.faceYaw
            rig.root.rotation.y = actor.yaw
            rig.root.scale.setScalar(actor.scale)
          }
        } else if (t >= 0) {
          applyAct(actor, move.act.at(t, actor.faceYaw), dt, time)
          stepEyes(actor, dt, time)
          return
        }
      }
    }

    // Walking: straight to the target, turning to face where it goes.
    let walking = false
    if (actor.walkTo) {
      const position = rig.root.position
      const toGo = actor.walkTo.clone().sub(position).setY(0)
      const distance = toGo.length()
      if (distance < 0.015) {
        position.copy(actor.walkTo)
        actor.walkTo = null
        if (!delivery || delivery.from !== actor.id) actor.targetYaw = actor.faceYaw // arrived: face the way its place faces
      } else {
        walking = true
        position.add(toGo.multiplyScalar(Math.min(1, (WALK_SPEED * dt) / distance)))
        actor.targetYaw = Math.atan2(actor.walkTo.x - position.x, actor.walkTo.z - position.z)
      }
    }
    actor.shadow.position.set(rig.root.position.x, 0.003, rig.root.position.z)

    // Turning the shortest way round.
    let turn = actor.targetYaw - actor.yaw
    turn = Math.atan2(Math.sin(turn), Math.cos(turn))
    actor.yaw += turn * Math.min(1, dt * 7)

    // A greeting (pointer on the robot) can take over any joint for a moment.
    let pose: Pose = {}
    if (actor.greeting !== null) {
      const greeting = GREETINGS[actor.id]
      actor.greeting += dt
      if (actor.greeting >= greeting.duration) {
        actor.greeting = null
        actor.greetAgain = time + 0.6
        options.onGreeting(null)
      } else if (!still) {
        pose = greeting.pose(actor.greeting, greeting.duration)
      }
    }

    // Legs and arms: a walking stride, or standing.
    if (walking) actor.stride += dt * 10
    const swing = walking ? Math.sin(actor.stride) : 0
    rig.leftLeg.upper.rotation.x = ease(rig.leftLeg.upper.rotation.x, swing * 0.55, 18, dt)
    rig.rightLeg.upper.rotation.x = ease(rig.rightLeg.upper.rotation.x, -swing * 0.55, 18, dt)
    rig.leftLeg.lower.rotation.x = ease(rig.leftLeg.lower.rotation.x, walking ? Math.max(0, -swing) * 0.7 : 0, 18, dt)
    rig.rightLeg.lower.rotation.x = ease(rig.rightLeg.lower.rotation.x, walking ? Math.max(0, swing) * 0.7 : 0, 18, dt)
    const bob = walking ? Math.abs(Math.sin(actor.stride)) * 0.018 : still ? 0 : Math.sin(time * 2 + actor.offset) * 0.004
    rig.body.position.y = HIP + bob
    rig.root.position.y = pose.lift ?? 0
    rig.root.rotation.y = actor.yaw + (pose.spin ?? 0)
    rig.body.rotation.x = ease(rig.body.rotation.x, pose.lean ?? 0, 12, dt)
    rig.body.rotation.z = ease(rig.body.rotation.z, pose.tilt ?? 0, 12, dt)

    const working = actor.status === 'working'
    const typing = working && !walking && !still ? Math.sin(time * 9 + actor.offset) * 0.12 : 0
    const leftArmTarget = walking ? -swing * 0.45 : working ? -0.55 + typing : 0
    const rightArmRest = walking ? swing * 0.45 : working ? -0.55 - typing : 0
    const elbowRest = working && !walking ? -0.7 : -0.12
    const arms = 16
    rig.leftArm.upper.rotation.x = ease(rig.leftArm.upper.rotation.x, pose.lUpX ?? leftArmTarget, arms, dt)
    rig.rightArm.upper.rotation.x = ease(rig.rightArm.upper.rotation.x, pose.rUpX ?? rightArmRest + (-1.35 - rightArmRest) * actor.reach, arms, dt)
    rig.leftArm.upper.rotation.z = ease(rig.leftArm.upper.rotation.z, pose.lUpZ ?? -0.12, arms, dt)
    rig.rightArm.upper.rotation.z = ease(rig.rightArm.upper.rotation.z, pose.rUpZ ?? 0.12, arms, dt)
    rig.leftArm.lower.rotation.x = ease(rig.leftArm.lower.rotation.x, pose.lLowX ?? elbowRest, arms, dt)
    rig.rightArm.lower.rotation.x = ease(rig.rightArm.lower.rotation.x, pose.rLowX ?? elbowRest * (1 - actor.reach), arms, dt)
    rig.leftArm.lower.rotation.z = ease(rig.leftArm.lower.rotation.z, pose.lLowZ ?? 0, arms, dt)
    rig.rightArm.lower.rotation.z = ease(rig.rightArm.lower.rotation.z, pose.rLowZ ?? 0, arms, dt)

    // The head: looks around while it works (or follows the greeting).
    const look = pose.headY ?? actor.headTurn ?? (working && !walking && !still ? Math.sin(time * 1.3 + actor.offset) * 0.32 : 0)
    rig.head.rotation.y = ease(rig.head.rotation.y, look, actor.greeting !== null ? 12 : 4, dt)
    rig.head.rotation.x = ease(rig.head.rotation.x, pose.headX ?? 0, 12, dt)
    rig.head.rotation.z = ease(rig.head.rotation.z, pose.headZ ?? 0, 12, dt)

    stepEyes(actor, dt, time)
  }

  const draw = (timeMs: number) => {
    frame = 0
    const dt = last ? Math.min(0.05, (timeMs - last) / 1000) : 1 / 60
    // Coming and going follow the real clock, but its steps are smoothed: one slow frame (the page doing other work)
    // would otherwise make the flyer jump ahead, and the next frames would look like a stutter.
    const rawDt = last ? Math.min(0.1, (timeMs - last) / 1000) : 1 / 60
    stepDt += (rawDt - stepDt) * 0.25
    const realDt = stepDt
    last = timeMs
    elapsed += dt

    stepDelivery(dt)
    for (const actor of Object.values(actors)) stepActor(actor, dt, elapsed, realDt)
    const smoking = smoke.update(realDt)
    for (let index = ripples.length - 1; index >= 0; index--) {
      const ripple = ripples[index]
      ripple.age += dt
      const grow = 0.2 + ripple.age * 1.6
      ripple.mesh.scale.set(grow, grow, grow)
      ;(ripple.mesh.material as MeshBasicMaterial).opacity = Math.max(0, 0.6 - ripple.age * 0.45)
      if (ripple.age > 1.35) {
        scene.remove(ripple.mesh)
        ;(ripple.mesh.material as MeshBasicMaterial).dispose()
        ripples.splice(index, 1)
      }
    }
    if (staticCableUntil && elapsed > staticCableUntil) {
      staticCableUntil = 0
      removeCable()
    }

    renderFrame(smoking || Object.values(actors).some((actor) => actor.move !== null))
    reportLabels()

    const greeting = Object.values(actors).some((actor) => actor.greeting !== null)
    const moves = Object.values(actors).some((actor) => actor.move !== null || actor.walkTo !== null)
    const busy = live || greeting || moves || smoking || delivery !== null || queue.length > 0 || ripples.length > 0 || elapsed < wakeUntil
    if (leaving && Object.values(actors).every((actor) => actor.gone)) {
      const done = leaving
      leaving = null
      done()
    }
    if (busy && visible) frame = requestAnimationFrame(draw)
    else last = 0
  }

  function start() {
    if (!frame && visible) frame = requestAnimationFrame(draw)
  }

  /**
   * The camera's frustum, widened from the panel to the whole window: the panel's rectangle keeps exactly the view a
   * panel-sized canvas had (same camera, same fit), and the rest of the window extends it in every direction.
   */
  const applyWindowProjection = () => {
    const near = camera.near
    const top = near * Math.tan(MathUtils.degToRad(camera.fov / 2))
    const right = top * camera.aspect
    const perPixel = (2 * top) / panel.height
    const left = -right - panel.x * perPixel
    const upper = top + panel.y * perPixel
    camera.projectionMatrix.makePerspective(left, left + view.width * perPixel, upper, upper - view.height * perPixel, near, camera.far)
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert()
  }

  /**
   * Draws a frame. Everything is drawn exactly ONCE: drawing a see-through thing (smoke, a glow) twice makes it
   * twice as dense, and the panel's rectangle would show up as a box inside the smoke.
   *   - Normally the whole scene is drawn inside the panel's rectangle (the scissor).
   *   - While anything is in the air (a robot flying on or off, or smoke still drifting), the floor things are drawn
   *     inside the panel first, and then the "air" layer (robots, their packs and the smoke) over the whole window.
   */
  const renderFrame = (inAir: boolean) => {
    renderer.setScissorTest(false)
    renderer.clear()
    const x = Math.max(0, clip.x)
    const y = Math.max(0, clip.y)
    const width = Math.max(0, Math.min(view.width, clip.x + clip.width) - x)
    const height = Math.max(0, Math.min(view.height, clip.y + clip.height) - y)
    renderer.setScissorTest(true)
    renderer.setScissor(x, view.height - y - height, width, height) // the scissor counts from the bottom
    if (inAir) camera.layers.set(GROUND_LAYER)
    else camera.layers.enableAll()
    renderer.render(scene, camera)
    renderer.setScissorTest(false)
    if (inAir) {
      camera.layers.set(AIR_LAYER)
      renderer.render(scene, camera)
    }
    camera.layers.enableAll()
  }

  // Name labels under each robot's feet, in CSS pixels.
  const projected = new Vector3()
  const reportLabels = () => {
    // Projected onto the whole window, then made relative to the panel (the labels live in the panel).
    const positions = {} as Record<AgentId, { x: number; y: number; headY: number; hidden: boolean }>
    for (const actor of Object.values(actors)) {
      projected.copy(actor.rig.root.position).setY(0).project(camera)
      const x = (projected.x * 0.5 + 0.5) * view.width - panel.x
      const y = (-projected.y * 0.5 + 0.5) * view.height - panel.y
      projected.copy(actor.rig.root.position).setY(1.02 * actor.rig.root.scale.y).project(camera)
      // A robot that is not standing on the stage (off it, or on its way on or off) has no name tag: the tag would stick to the edge.
      positions[actor.id] = { x, y, headY: (-projected.y * 0.5 + 0.5) * view.height - panel.y, hidden: actor.gone || actor.move !== null }
    }
    options.onLabels(positions)
  }

  /**
   * Moves the camera along its line of view until every robot (its feet,
   * sides and the top of its head, with a margin) fits the box. The box is a
   * different shape on a phone, a tablet and a desktop, so this runs on
   * every resize instead of using one fixed distance.
   */
  const fitCamera = () => {
    const direction = CAMERA.clone().sub(LOOK_AT)
    const corners: Vector3[] = []
    for (const agent of AGENTS) {
      const [x, z] = HOMES[agent.id]
      const height = (agent.id === 'lead' ? LEAD_SCALE : ROBOT_SCALE) * 1.0
      corners.push(new Vector3(x - 0.28, 0, z), new Vector3(x + 0.28, 0, z), new Vector3(x, height, z), new Vector3(x, -0.05, z + 0.2))
      if (NAME_ABOVE.has(agent.id)) corners.push(new Vector3(x, height + 0.24, z)) // room for the name above its head
    }
    const point = new Vector3()
    for (let factor = 0.6; factor <= 2.5; factor += 0.02) {
      camera.position.copy(LOOK_AT).add(direction.clone().multiplyScalar(factor))
      camera.lookAt(LOOK_AT)
      camera.updateProjectionMatrix()
      camera.updateMatrixWorld()
      // Leave room at the top for the speech bubbles and at the bottom for the names.
      const fits = corners.every((corner) => {
        point.copy(corner).project(camera)
        return Math.abs(point.x) < 0.96 && point.y < 0.74 && point.y > -0.86
      })
      if (fits) return
    }
  }

  /** Starts a robot's greeting, unless it is busy walking or carrying a message. */
  const greet = (id: AgentId) => {
    const actor = actors[id]
    if (actor.gone || actor.move) return
    const busyWithMessage = delivery !== null && (delivery.from === id || delivery.to === id)
    if (actor.greeting !== null || actor.walkTo || busyWithMessage || elapsed < actor.greetAgain) return
    for (const other of Object.values(actors)) other.greeting = null // one hello at a time
    actor.greeting = 0
    options.onGreeting(id)
    wake()
  }

  const raycaster = new Raycaster()
  raycaster.layers.enableAll() // the robots live on the air layer
  const pointer = new Vector2()
  const robots = Object.values(actors).map((actor) => actor.rig.root)
  let pointed: AgentId | null = null
  const pointAt = (x: number | null, y: number | null): AgentId | null => {
    if (x === null || y === null) {
      pointed = null
      return null
    }
    // x and y are inside the panel; the camera projects onto the whole window.
    pointer.set(((x + panel.x) / view.width) * 2 - 1, -((y + panel.y) / view.height) * 2 + 1)
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObjects(robots, true)[0]
    const id = hit ? (owner.get(hit.object.id) ?? null) : null
    if (id && id !== pointed) greet(id)
    pointed = id
    return id
  }

  const faceTowardLead = (actor: Actor) =>
    actor.id === 'lead' ? actor.homeYaw : Math.atan2(actors.lead.home.x - actor.station.x, actors.lead.home.z - actor.station.z)

  return {
    pointAt,
    greet,
    enter() {
      for (const actor of Object.values(actors)) {
        actor.gone = false
        actor.walkTo = null
        if (options.reducedMotion) {
          actor.rig.root.visible = true
          actor.shadow.visible = true
          actor.rig.root.position.copy(actor.station)
          continue
        }
        actor.move = { kind: 'enter', act: ARRIVALS[actor.id], time: 0, started: false }
        actor.rig.root.visible = false // until its own start time
        actor.shadow.visible = false
      }
      wake()
    },
    exit() {
      if (options.reducedMotion) return Promise.resolve()
      queue.length = 0
      return new Promise<void>((resolve) => {
        leaving = resolve
        for (const actor of Object.values(actors)) {
          if (actor.gone) continue
          if (actor.move?.kind === 'enter' && actor.move.time < actor.move.act.delay) {
            actor.move = null // it had not come on yet: it simply stays off
            actor.gone = true
            continue
          }
          actor.walkTo = null
          actor.greeting = null
          actor.move = { kind: 'exit', act: DEPARTURES[actor.id], time: 0, started: false }
        }
        options.onGreeting(null)
        wake()
      })
    },
    setHuddle(on) {
      for (const agent of AGENTS) {
        const actor = actors[agent.id]
        const [x, z] = on ? HUDDLE[agent.id] : HOMES[agent.id]
        actor.station = new Vector3(x, 0, z)
        actor.faceYaw = on ? faceTowardLead(actor) : actor.homeYaw
        if (actor.gone || actor.move) continue
        if (options.reducedMotion) {
          actor.rig.root.position.copy(actor.station)
          actor.yaw = actor.targetYaw = actor.faceYaw
        } else if (!delivery || (delivery.from !== agent.id)) {
          actor.walkTo = actor.station.clone()
        }
      }
      wake()
    },
    update(team) {
      live = team.live && !options.reducedMotion
      for (const agent of AGENTS) actors[agent.id].status = team.agents[agent.id].status

      for (const message of team.messages) {
        if (seenMessages.has(message.id)) continue
        seenMessages.add(message.id)
        if (firstUpdate) continue // messages from before the corner opened are not replayed
        const from = message.from === 'team' ? 'lead' : message.from
        if (message.to === 'team') {
          if (!options.reducedMotion) sendRipple(actors[from])
          continue
        }
        if (message.to === from) continue
        queue.push({ from, to: message.to })
        if (queue.length > 3) queue.shift() // a burst of messages: keep the newest (three: the options hand-over)
      }
      firstUpdate = false
      wake()
    },
    place(nextPanel, nextClip, viewWidth, viewHeight) {
      if (nextPanel.width < 1 || nextPanel.height < 1 || viewWidth < 1 || viewHeight < 1) return
      const resized = nextPanel.width !== panel.width || nextPanel.height !== panel.height
      const viewChanged = viewWidth !== view.width || viewHeight !== view.height
      panel = nextPanel
      clip = nextClip
      view = { width: viewWidth, height: viewHeight }
      if (viewChanged) {
        // A big window at a high pixel ratio is a large layer: keep it under about eight million pixels.
        const ratio = Math.min(window.devicePixelRatio, 2, Math.sqrt(8_000_000 / (viewWidth * viewHeight)))
        renderer.setPixelRatio(Math.max(1, ratio))
        renderer.setSize(viewWidth, viewHeight, false)
      }
      if (resized) {
        camera.aspect = panel.width / panel.height
        fitCamera() // fitted to the PANEL, exactly as before
      }
      applyWindowProjection()
      wake(0.2)
    },
    waveAll() {
      if (options.reducedMotion) return
      for (const actor of Object.values(actors)) {
        if (actor.gone || actor.move) continue
        actor.greeting = 0
      }
      wake()
    },
    hide() {
      for (const actor of Object.values(actors)) {
        actor.move = null
        actor.walkTo = null
        actor.gone = true
        actor.rig.root.visible = false
        actor.shadow.visible = false
      }
      wake(0.1)
    },
    setVisible(next) {
      visible = next
      if (visible) wake(0.5)
      else if (frame) {
        cancelAnimationFrame(frame)
        frame = 0
        last = 0
      }
    },
    dispose() {
      if (frame) cancelAnimationFrame(frame)
      removeCable()
      for (const ripple of ripples) (ripple.mesh.material as MeshBasicMaterial).dispose()
      for (const actor of Object.values(actors)) {
        actor.prop.dispose()
        actor.floorGlow.dispose()
        ;(actor.shadow.material as MeshBasicMaterial).dispose()
        actor.rig.dispose()
      }
      smoke.dispose()
      for (const item of disposables) item.dispose()
    },
  }
}
