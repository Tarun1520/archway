import {
  ACESFilmicToneMapping,
  AdditiveBlending,
  BackSide,
  BoxGeometry,
  CanvasTexture,
  CircleGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Group,
  HemisphereLight,
  InstancedMesh,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  Object3D,
  OrthographicCamera,
  PerspectiveCamera,
  Plane,
  PMREMGenerator,
  PointLight,
  Scene,
  SRGBColorSpace,
  TorusGeometry,
  Vector3,
  WebGLRenderer,
} from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { ArchyAction } from '../../../../content/archy'
import { speakingLevel } from '../../../../lib/voice/speaker'
import { buildRobot, createRobotMaterials, HIP } from '../../agents/three/buildRobot'
import { ARCHY_POSES, TRICK_NAMES, TRICKS, type ArchyBody, type TrickName } from './archyPoses'

/**
 * Archy on his portal, in 3D: the same robot the agents use (buildRobot.ts),
 * in blue, floating on a column of air that rushes up out of the portal.
 *
 *   awake    the air lifts him out of the portal (the part still below it is
 *            cut away, so he really comes up out of the light) and he hangs
 *            there, bobbing and swaying, legs dangling, arms a little out.
 *            Whatever setAction() says he acts out on top of that: wave,
 *            point, listen, think ... (archyPoses.ts has one pose per action).
 *   idle     with nothing to say, now and then he plays in the air: a
 *            skydiving pose, an air flip, a roll, a pirouette, swimming, a
 *            flail in a gust (TRICKS in archyPoses.ts).
 *   asleep   he drops back onto the portal and sinks in; the portal dims and
 *            breathes slowly.
 *   voice    his eyes and collar glow brighter and his head nods a little
 *            while he speaks (read from the loudness of his own voice), and
 *            the portal's ring of lights follows the person's voice.
 *
 * TWO LAYOUTS
 *   dock     (default) a small stage with a perspective camera: the portal
 *            fills the canvas and he floats above it. Used where there is no
 *            room for the strip (the phone-sized drawer).
 *   strip    setPlacement({...}) switches to a wide canvas along the bottom
 *            of the window, drawn with a tilted flat (orthographic) camera.
 *            The portal is drawn at the spot given, and he can float up past
 *            the top of the portal's own box, because the canvas reaches
 *            well above it.
 *
 * Plain three.js, no React (ArchyStage3D.tsx wraps it). It draws every frame
 * while visible, but only about 20 times a second when Archy is away.
 */

export interface ArchyPlacement {
  /** Where the portal's middle is on the canvas, in CSS pixels from its top left. */
  x: number
  y: number
  /** How many CSS pixels one world unit (about Archy's height) is. */
  scale: number
}

/** Where Archy is on screen, in the canvas's CSS pixels: reported every drawn frame in the strip layout. */
export interface RobotScreen {
  x: number
  /** Feet. */
  y: number
  /** Height of his body, for the click target. */
  height: number
  visible: boolean
}

export interface ArchyStageOptions {
  reducedMotion: boolean
  onRobot?: (robot: RobotScreen) => void
}

export interface ArchyStage {
  setAction(action: ArchyAction): void
  setAwake(awake: boolean): void
  /** How loud the microphone is right now (0 silent, about 0.1 loud speech). */
  setMicLevel(level: number): void
  /** Strip layout (a placement) or dock layout (null). */
  setPlacement(placement: ArchyPlacement | null): void
  /** Whether he plays tricks in the air when he has nothing to say. */
  setTricks(tricks: boolean): void
  /** Plays one trick now (for tests and demos): ignored unless he is floating. */
  playTrick(name: TrickName): void
  resize(width: number, height: number): void
  setVisible(visible: boolean): void
  dispose(): void
}

const BLUE_SHELL = '#1a73ff'
const CYAN = new Color('#8be9ff')
const BASE = 0.03 // the height of the portal's glowing surface
const SINK = 1.3 // how far below the surface he waits
const HOVER = 0.5 // how high the air holds him above the portal
const CENTER = 0.55 // his middle, from his feet: flips turn about this point
const RISE_SECONDS = 1.5
const CAMERA = new Vector3(0, 1.55, 4.7)
const LOOK_AT = new Vector3(0, 0.8, 0)
const TICKS = 28
// Flat on his belly, he is turned this far from facing the viewer (nearly side-on), so the arch of a skydiver reads clearly.
const DIVE_TURN = 1.35
const STREAKS = 26

// The strip layout's flat camera looks down at this angle.
const TILT = (20 * Math.PI) / 180
const SIN = Math.sin(TILT)
const COS = Math.cos(TILT)

function softTexture(stops: [number, string][], size = 128): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const context = canvas.getContext('2d')!
  const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  for (const [at, colour] of stops) gradient.addColorStop(at, colour)
  context.fillStyle = gradient
  context.fillRect(0, 0, size, size)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  return texture
}

/** A tall fade: opaque at the bottom, clear at the top (the column of air). */
function beamTexture(): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 4
  canvas.height = 128
  const context = canvas.getContext('2d')!
  const gradient = context.createLinearGradient(0, 0, 0, 128)
  gradient.addColorStop(0, 'rgba(210,235,255,0)')
  gradient.addColorStop(0.55, 'rgba(210,235,255,0.35)')
  gradient.addColorStop(1, 'rgba(235,246,255,0.95)')
  context.fillStyle = gradient
  context.fillRect(0, 0, 4, 128)
  return new CanvasTexture(canvas)
}

const smooth = (k: number) => k * k * (3 - 2 * k)
const ease = (from: number, to: number, rate: number, dt: number) => from + (to - from) * Math.min(1, dt * rate)
/** A repeatable pseudo-random number from a whole number (so the air streaks do not need stored randomness). */
const hash = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453
  return x - Math.floor(x)
}

export function createArchyStage(canvas: HTMLCanvasElement, options: ArchyStageOptions): ArchyStage {
  // Throws when WebGL is not available; the wrapper then shows a flat portal instead.
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.outputColorSpace = SRGBColorSpace
  renderer.localClippingEnabled = true // lets him be cut off below the portal while he rises

  const scene = new Scene()
  const dockCamera = new PerspectiveCamera(30, 1.2, 0.1, 40)
  dockCamera.position.copy(CAMERA)
  dockCamera.lookAt(LOOK_AT)
  const stripCamera = new OrthographicCamera(-1, 1, 1, -1, 0.1, 80)
  stripCamera.position.set(0, SIN * 30, COS * 30)
  stripCamera.lookAt(0, 0, 0)
  let camera: PerspectiveCamera | OrthographicCamera = dockCamera

  const environmentMaker = new PMREMGenerator(renderer)
  const environment = environmentMaker.fromScene(new RoomEnvironment(), 0.04).texture
  scene.environment = environment
  scene.environmentIntensity = 0.55
  scene.add(new HemisphereLight('#ffffff', '#202030', 0.55))
  const key = new DirectionalLight('#ffffff', 2.1)
  key.position.set(2.5, 5, 4)
  scene.add(key)
  const rim = new DirectionalLight('#8fc8ff', 1.3)
  rim.position.set(-3, 2.5, -4)
  scene.add(rim)
  // The portal lights him from below.
  const portalLight = new PointLight('#6fa8ff', 0, 3.6, 1.4)
  portalLight.position.set(0, 0.35, 0.5)
  scene.add(portalLight)

  const owned: { dispose(): void }[] = [renderer, environment, environmentMaker]

  // --- The portal -------------------------------------------------------------------
  const portal = new Group()
  scene.add(portal)

  const plateMaterial = new MeshStandardMaterial({ color: '#0d0f18', roughness: 0.5, metalness: 0.5 })
  const lowerGeometry = new CylinderGeometry(1.0, 1.06, 0.07, 56)
  const lower = new Mesh(lowerGeometry, plateMaterial)
  lower.position.y = -0.04
  portal.add(lower)
  const upperGeometry = new CylinderGeometry(0.86, 0.92, 0.05, 56)
  const upper = new Mesh(upperGeometry, new MeshStandardMaterial({ color: '#151826', roughness: 0.4, metalness: 0.6 }))
  upper.position.y = 0.0
  portal.add(upper)
  const rimGeometry = new TorusGeometry(1.03, 0.012, 8, 72)
  const rimMaterial = new MeshBasicMaterial({ color: '#5a5ff0', toneMapped: false })
  const rimRing = new Mesh(rimGeometry, rimMaterial)
  rimRing.rotation.x = Math.PI / 2
  rimRing.position.y = -0.01
  portal.add(rimRing)

  const coreTexture = softTexture([[0, '#ffffff'], [0.55, '#eaf5ff'], [0.82, '#8fc2ff'], [1, 'rgba(61,107,255,0)']])
  const coreGeometry = new CircleGeometry(0.66, 48)
  const coreMaterial = new MeshBasicMaterial({ map: coreTexture, transparent: true, toneMapped: false, depthWrite: false })
  const core = new Mesh(coreGeometry, coreMaterial)
  core.rotation.x = -Math.PI / 2
  core.position.y = BASE - 0.003
  portal.add(core)

  // The ring of light ticks, turning slowly.
  const ticks = new Group()
  const tickGeometry = new BoxGeometry(0.1, 0.012, 0.03)
  const tickMaterial = new MeshBasicMaterial({ color: '#f2f8ff', toneMapped: false })
  for (let index = 0; index < TICKS; index++) {
    const angle = (index / TICKS) * Math.PI * 2
    const tick = new Mesh(tickGeometry, tickMaterial)
    tick.position.set(Math.cos(angle) * 0.76, BASE, Math.sin(angle) * 0.76)
    tick.rotation.y = -angle
    ticks.add(tick)
  }
  portal.add(ticks)

  // A soft glow on the floor around the portal.
  const haloTexture = softTexture([[0, 'rgba(120,170,255,0.55)'], [1, 'rgba(120,170,255,0)']])
  const haloGeometry = new CircleGeometry(1.7, 48)
  const haloMaterial = new MeshBasicMaterial({ map: haloTexture, transparent: true, depthWrite: false, blending: AdditiveBlending, toneMapped: false })
  const halo = new Mesh(haloGeometry, haloMaterial)
  halo.rotation.x = -Math.PI / 2
  halo.position.y = -0.07
  portal.add(halo)

  // The column of air going up.
  const beamMap = beamTexture()
  const beamGeometry = new CylinderGeometry(0.5, 0.64, 2.3, 40, 1, true)
  const beamMaterial = new MeshBasicMaterial({
    map: beamMap, color: '#b4dcff', transparent: true, opacity: 0, depthWrite: false, blending: AdditiveBlending, side: BackSide, toneMapped: false,
  })
  const beam = new Mesh(beamGeometry, beamMaterial)
  beam.position.y = 1.15 + BASE
  portal.add(beam)

  // Streaks of air rushing up through it: thin lines that rise, stretch and fade out at the top.
  const streakGeometry = new BoxGeometry(0.014, 0.34, 0.014)
  const streakMaterial = new MeshBasicMaterial({ color: '#e4f2ff', transparent: true, opacity: 0, depthWrite: false, blending: AdditiveBlending, toneMapped: false })
  const streaks = new InstancedMesh(streakGeometry, streakMaterial, STREAKS)
  streaks.frustumCulled = false
  portal.add(streaks)
  const dummy = new Object3D()

  owned.push(
    plateMaterial, lowerGeometry, upperGeometry, upper.material as MeshStandardMaterial, rimGeometry, rimMaterial,
    coreTexture, coreGeometry, coreMaterial, tickGeometry, tickMaterial, haloTexture, haloGeometry, haloMaterial,
    beamMap, beamGeometry, beamMaterial, streakGeometry, streakMaterial, { dispose: () => streaks.dispose() },
  )

  // --- Archy: the agents' robot, in blue ---------------------------------------------
  const materials = createRobotMaterials()
  const shell = new MeshPhysicalMaterial({ color: BLUE_SHELL, roughness: 0.34, metalness: 0.08, clearcoat: 0.75, clearcoatRoughness: 0.14 })
  const rig = buildRobot(materials, { shell, glow: CYAN.getStyle() })
  const clip = new Plane(new Vector3(0, 1, 0), -BASE) // keeps everything above the portal's surface
  for (const material of [materials.shell, materials.joint, materials.visor, shell, rig.glow, rig.codeLayer.material as MeshBasicMaterial]) {
    material.clippingPlanes = [clip]
  }
  // He hangs from a pivot at his middle, so flips and rolls turn him about his centre, not his feet.
  const pivot = new Group()
  pivot.rotation.order = 'YXZ' // turn about the up axis last: a dive (pitch) is then seen from the side once he is turned
  pivot.visible = false
  rig.root.position.set(0, -CENTER, 0)
  pivot.add(rig.root)
  scene.add(pivot)
  owned.push(materials.shell, materials.joint, materials.visor, shell, { dispose: () => rig.dispose() })

  // --- State -----------------------------------------------------------------------------
  const motion = options.reducedMotion ? 0 : 1
  let action: ArchyAction = 'idle'
  let actionTime = 0
  let awake = false
  let rise = 0 // 0 in the portal, 1 floating
  let mic = 0
  let energy = 0
  let voice = 0
  let visible = true
  let frame = 0
  let last = 0
  let elapsed = 0
  let nextBlink = 2
  let blink = 0
  let width = 0
  let height = 0

  let placement: ArchyPlacement | null = null
  let tricksOn = true
  // The trick he is playing now (and for how long so far), and when he next feels like one.
  let trick: { name: TrickName; time: number } | null = null
  let lastTrick: TrickName | null = null
  let nextTrick = 4
  // Smoothed whole-body angles, so a trick ending glides back to floating.
  const turn = { flip: 0, roll: 0, dive: 0, spin: 0, rise: 0 }

  /** Frames the strip's flat camera so the portal's middle lands on the placement. */
  const fitStripCamera = () => {
    if (!placement || width <= 0 || height <= 0) return
    const unit = placement.scale
    stripCamera.left = -placement.x / unit
    stripCamera.right = (width - placement.x) / unit
    stripCamera.top = placement.y / unit
    stripCamera.bottom = -(height - placement.y) / unit
    stripCamera.updateProjectionMatrix()
  }

  const chooseTrick = () => {
    let name = TRICK_NAMES[Math.floor(Math.random() * TRICK_NAMES.length)]
    if (name === lastTrick) name = TRICK_NAMES[(TRICK_NAMES.indexOf(name) + 1) % TRICK_NAMES.length]
    lastTrick = name
    trick = { name, time: 0 }
  }

  const step = (dt: number) => {
    elapsed += dt
    actionTime += dt

    // --- Rising, floating and sinking -----------------------------------------------
    rise = Math.min(1, Math.max(0, rise + (awake ? dt : -dt) / RISE_SECONDS))
    const lifted = smooth(rise)
    pivot.visible = rise > 0.001
    clip.constant = rise >= 1 ? 8 : -BASE // fully up in the air: nothing is cut away any more
    const settled = rise >= 1

    // --- Quiet moments: tricks. Never while he speaks or anyone is speaking to him. ------------
    voice = ease(voice, speakingLevel(), 22, dt)
    const quiet = (action === 'idle' || action === 'listen') && voice < 0.04 && mic < 0.012
    if (!(tricksOn && motion === 1 && awake && settled && quiet)) {
      if (trick && !quiet) trick = null // somebody spoke: stop, glide back to floating
      nextTrick = Math.max(nextTrick, elapsed + 3) // a pause before the next one
    } else if (!trick && elapsed >= nextTrick) {
      chooseTrick()
    }
    let body: ArchyBody = {}
    if (trick) {
      trick.time += dt
      const def = TRICKS[trick.name]
      body = def.pose(trick.time, motion, def.duration)
      if (trick.time >= def.duration) {
        trick = null
        nextTrick = elapsed + 6 + Math.random() * 6
      }
    } else if (settled || awake) {
      body = ARCHY_POSES[action](actionTime, motion)
    }

    // --- Where his middle is and how it is turned --------------------------------------------
    // y of his feet runs from SINK below the portal to HOVER above it.
    const bob = motion ? Math.sin(elapsed * 1.7) * 0.05 : 0
    const feet = BASE - SINK + (SINK + HOVER) * lifted + (settled ? bob : 0)
    turn.rise = ease(turn.rise, (body.rise ?? 0) + (body.lift ?? 0), 10, dt)
    // Whole turns are wrapped to one lap, so a flip that ended on a full turn is simply upright again,
    // and the next pose does not spin him back round.
    const lap = 2 * Math.PI
    turn.flip = (body.flip ?? 0) % lap
    turn.roll = (body.roll ?? 0) % lap
    turn.spin = (body.spin ?? 0) % lap
    turn.dive = ease(turn.dive, body.dive ?? 0, 9, dt)
    pivot.position.set(0, feet + CENTER + (settled ? turn.rise : 0), 0)
    const sway = motion && settled ? Math.sin(elapsed * 1.1) * 0.05 : 0
    const pitch = motion && settled ? Math.sin(elapsed * 0.9) * 0.04 : 0
    pivot.rotation.set(turn.flip + pitch + turn.dive * Math.PI * 0.46, turn.spin + turn.dive * DIVE_TURN, turn.roll + sway)

    // --- Limbs: arms from the pose; legs dangle and drift in the air unless the pose says otherwise ------
    const arms = 14
    rig.leftArm.upper.rotation.x = ease(rig.leftArm.upper.rotation.x, body.lUpX ?? 0, arms, dt)
    rig.rightArm.upper.rotation.x = ease(rig.rightArm.upper.rotation.x, body.rUpX ?? 0, arms, dt)
    // Floating, his arms rest a little out, as if balancing on the air.
    rig.leftArm.upper.rotation.z = ease(rig.leftArm.upper.rotation.z, body.lUpZ ?? -0.45, arms, dt)
    rig.rightArm.upper.rotation.z = ease(rig.rightArm.upper.rotation.z, body.rUpZ ?? 0.45, arms, dt)
    rig.leftArm.lower.rotation.x = ease(rig.leftArm.lower.rotation.x, body.lLowX ?? -0.2, arms, dt)
    rig.rightArm.lower.rotation.x = ease(rig.rightArm.lower.rotation.x, body.rLowX ?? -0.2, arms, dt)
    rig.leftArm.lower.rotation.z = ease(rig.leftArm.lower.rotation.z, body.lLowZ ?? 0, arms, dt)
    rig.rightArm.lower.rotation.z = ease(rig.rightArm.lower.rotation.z, body.rLowZ ?? 0, arms, dt)

    const drift = motion ? Math.sin(elapsed * 1.3) : 0
    const legs = 12
    rig.leftLeg.upper.rotation.x = ease(rig.leftLeg.upper.rotation.x, body.lLegX ?? 0.12 + drift * 0.07, legs, dt)
    rig.rightLeg.upper.rotation.x = ease(rig.rightLeg.upper.rotation.x, body.rLegX ?? 0.12 - drift * 0.07, legs, dt)
    rig.leftLeg.lower.rotation.x = ease(rig.leftLeg.lower.rotation.x, body.lKneeX ?? 0.4, legs, dt)
    rig.rightLeg.lower.rotation.x = ease(rig.rightLeg.lower.rotation.x, body.rKneeX ?? 0.4, legs, dt)
    rig.leftLeg.upper.rotation.z = ease(rig.leftLeg.upper.rotation.z, -(body.splay ?? 0.05), legs, dt)
    rig.rightLeg.upper.rotation.z = ease(rig.rightLeg.upper.rotation.z, body.splay ?? 0.05, legs, dt)

    rig.body.rotation.x = ease(rig.body.rotation.x, body.lean ?? 0, 10, dt)
    rig.body.rotation.z = ease(rig.body.rotation.z, body.tilt ?? 0, 10, dt)
    rig.body.position.y = HIP

    // Speaking: the head nods a little with his own voice.
    const talkNod = motion ? Math.sin(elapsed * 11) * voice * 0.05 : 0
    rig.head.rotation.y = ease(rig.head.rotation.y, body.headY ?? 0, 6, dt)
    rig.head.rotation.x = ease(rig.head.rotation.x, (body.headX ?? 0) + talkNod, 12, dt)
    rig.head.rotation.z = ease(rig.head.rotation.z, body.headZ ?? 0, 8, dt)

    // Eyes and collar: brighter with his voice or the person's voice; a blink now and then.
    energy = ease(energy, Math.min(1, Math.max(voice, mic * 9)), 16, dt)
    rig.glow.color.copy(CYAN).multiplyScalar(0.95 + energy * 1.3)
    if (motion && elapsed > nextBlink) {
      blink = 0.14
      nextBlink = elapsed + 3 + ((elapsed * 7.3) % 3)
    }
    blink = Math.max(0, blink - dt)
    for (const eye of rig.eyes) eye.scale.y = ease(eye.scale.y, blink > 0 ? 0.12 : 1, 30, dt)

    // --- The portal and its column of air ------------------------------------------------------
    ticks.rotation.y += dt * (awake ? 0.55 : 0.14) * motion
    const slow = motion ? 0.5 + 0.5 * Math.sin(elapsed * 1.7) : 0.5
    coreMaterial.color.setScalar((awake ? 1 : 0.35 + slow * 0.25) * 0.9 + energy * 0.25)
    haloMaterial.opacity = ease(haloMaterial.opacity, awake ? 0.85 : 0.3 + slow * 0.15, 4, dt)
    tickMaterial.color.setScalar((awake ? 0.8 : 0.3) + (awake ? Math.min(1, mic * 10) * 0.7 : 0))
    beamMaterial.opacity = ease(beamMaterial.opacity, awake ? 0.2 + Math.min(1, mic * 8) * 0.18 : 0, 4, dt)
    portalLight.intensity = ease(portalLight.intensity, awake ? 0.8 + energy * 0.9 : 0, 5, dt)

    // The air rushes up faster when he is held higher; each streak starts at the portal and fades at the top.
    streakMaterial.opacity = ease(streakMaterial.opacity, awake ? 0.3 : 0, 4, dt)
    for (let index = 0; index < STREAKS; index++) {
      const phase = hash(index + 1)
      const spin = hash(index + 71) * Math.PI * 2
      const radius = 0.12 + hash(index + 33) * 0.42
      const run = (phase + elapsed * (0.45 + hash(index + 9) * 0.35) * motion) % 1
      dummy.position.set(Math.cos(spin) * radius, BASE + run * 2.1, Math.sin(spin) * radius)
      const stretch = Math.sin(run * Math.PI) // short at both ends
      dummy.scale.set(1, 0.35 + stretch * 0.95, 1)
      dummy.updateMatrix()
      streaks.setMatrixAt(index, dummy.matrix)
    }
    streaks.instanceMatrix.needsUpdate = true
  }

  /** Tells the page where he is, so it can put a click target and a speech bubble on him. */
  const reportRobot = () => {
    if (!options.onRobot) return
    if (!placement) {
      options.onRobot({ x: 0, y: 0, height: 0, visible: false })
      return
    }
    const middle = placement.y - pivot.position.y * COS * placement.scale
    options.onRobot({
      x: placement.x,
      y: middle + CENTER * COS * placement.scale,
      height: 1.25 * COS * placement.scale,
      visible: pivot.visible && rise > 0.5,
    })
  }

  const draw = (timeMs: number) => {
    frame = 0
    if (!visible) {
      last = 0
      return
    }
    const sinceLast = last ? (timeMs - last) / 1000 : 1 / 60
    // Away and still: about 20 frames a second is plenty for a slow glow.
    const away = !awake && rise <= 0
    if (away && last && sinceLast < 0.05) {
      frame = requestAnimationFrame(draw)
      return
    }
    last = timeMs
    step(Math.min(0.05, sinceLast))
    renderer.render(scene, camera)
    reportRobot()
    frame = requestAnimationFrame(draw)
  }

  const start = () => {
    if (!frame && visible) frame = requestAnimationFrame(draw)
  }

  start()

  return {
    setAction(next) {
      if (next === action) return
      action = next
      actionTime = 0
      start()
    },
    setAwake(next) {
      awake = next
      if (!next) trick = null
      start()
    },
    setMicLevel(level) {
      mic = level
    },
    setPlacement(next) {
      placement = next
      camera = next ? stripCamera : dockCamera
      fitStripCamera() // the portal stays at the world's middle; only the camera moves
      start()
    },
    setTricks(next) {
      tricksOn = next
      if (!next) trick = null
    },
    playTrick(name) {
      if (awake && rise >= 1) trick = { name, time: 0 }
      start()
    },
    resize(w, h) {
      if (w <= 0 || h <= 0) return
      width = w
      height = h
      renderer.setSize(w, h, false)
      dockCamera.aspect = w / h
      // A narrow dock needs the camera further back to keep the portal in view.
      const needed = 2.15 / Math.max(dockCamera.aspect, 0.01)
      dockCamera.position.z = Math.max(CAMERA.z, needed / (2 * Math.tan((dockCamera.fov * Math.PI) / 360)) * 1.02)
      dockCamera.updateProjectionMatrix()
      dockCamera.lookAt(LOOK_AT)
      fitStripCamera()
      renderer.render(scene, camera)
    },
    setVisible(next) {
      visible = next
      if (next) start()
    },
    dispose() {
      cancelAnimationFrame(frame)
      frame = 0
      for (const item of owned) item.dispose()
    },
  }
}
