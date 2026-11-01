/**
 * How each robot flies onto the stage and off it, on a jetpack, moving the way a jetpack pilot really moves.
 *
 * THE PHYSICS IT FOLLOWS
 *   A jetpack can only push along the line of its nozzles. So to speed up, slow down or turn, the pilot tilts the
 *   whole body: the thrust it needs is  (its acceleration) + (gravity's pull upward).  The tilt of that vector is the
 *   body's tilt, and its length (in "g") is the engine's thrust: 1 = hovering, more when braking or climbing, less
 *   when dropping. Both come out of the flight path itself, so the body and the flames always match the motion:
 *     - coming in fast, it flares (tilts back) to brake, flames long;
 *     - over its spot it hovers, nearly upright, and lets itself down;
 *     - leaving, it lifts off upright, then tips forward toward where it goes and accelerates away.
 *   The path is a smooth curve through a few points, each with a speed and direction, so speed never jumps.
 *
 * LANDING   legs reach for the ground in the last moments, the knees take the touchdown (the body dips and rises),
 *           the jet kicks up a burst of dust, and the engine spools down with a last trail of smoke before the pack
 *           folds away.
 * TAKE-OFF  the pack unfolds, the engine sputters to life with smoke rolling over the floor, the knees load, then it
 *           lifts off (another burst of dust) and climbs away.
 *
 * Each robot comes from, and leaves toward, its own side of the screen: everyone uses the same jetpack, but each flight
 * is its own. Every path starts or ends outside the browser window (the team is drawn on a layer over the whole page
 * while it moves). An act takes 4 to 5 seconds; the team is staggered.
 *
 * `at(t, faceYaw)` gives the robot's state t seconds into its act, relative to its place on the stage.
 */
import type { AgentId } from '../../../../lib/agentTeam'
import type { PropFrame } from './teamProps'

/** Joint angles (radians). Left out = the resting angle. Positive leg/arm = swung back; positive knee = bent. */
export interface Limbs {
  lLeg: number
  rLeg: number
  lKnee: number
  rKnee: number
  lLegOut: number
  rLegOut: number
  lArm: number
  rArm: number
  lArmOut: number
  rArmOut: number
  lElbow: number
  rElbow: number
  headX: number
  headY: number
}

export interface ActFrame {
  /** Offset from its place on the stage (floor units), and the height of its feet above the floor. */
  x: number
  z: number
  lift: number
  /** Which way it faces (radians, 0 = toward the viewer); null = its place's own way. */
  yaw: number | null
  /** Whole-body tilt from the thrust: forward (positive) and sideways. */
  pitch: number
  roll: number
  /** Bend at the hips (forward is positive), on top of the whole-body tilt. */
  lean: number
  limbs: Partial<Limbs>
  prop: PropFrame | null
  /** Its velocity (floor units a second), so the exhaust can trail behind it. */
  velocity: [number, number, number]
  /** A burst of dust this frame (touchdown, lift-off). */
  burst?: number
}

export interface Act {
  duration: number
  delay: number
  at(t: number, faceYaw: number): ActFrame
}

const G = 9.8 // gravity, in floor units a second squared (a robot is about one unit tall, so one unit is about a metre)
const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v))
const lerp = (a: number, b: number, p: number) => a + (b - a) * p
const smooth = (p: number) => {
  const q = clamp(p)
  return q * q * (3 - 2 * q)
}
const window01 = (t: number, a: number, b: number) => smooth((t - a) / (b - a))

type V3 = [number, number, number]

/** One point the flight passes: when, where (relative to its spot), and how fast it is going there. */
interface Key {
  t: number
  p: V3
  v: V3
}

/** Position on the smooth curve through the keys (cubic Hermite: it passes each point at that point's velocity). */
function along(keys: Key[], t: number): V3 {
  if (t <= keys[0].t) return [...keys[0].p] as V3
  const last = keys[keys.length - 1]
  if (t >= last.t) return [last.p[0] + last.v[0] * (t - last.t), last.p[1] + last.v[1] * (t - last.t), last.p[2] + last.v[2] * (t - last.t)]
  let i = 0
  while (keys[i + 1].t < t) i++
  const a = keys[i]
  const b = keys[i + 1]
  const h = b.t - a.t
  const u = (t - a.t) / h
  const h00 = 2 * u ** 3 - 3 * u ** 2 + 1
  const h10 = u ** 3 - 2 * u ** 2 + u
  const h01 = -2 * u ** 3 + 3 * u ** 2
  const h11 = u ** 3 - u ** 2
  return [0, 1, 2].map((k) => h00 * a.p[k] + h10 * h * a.v[k] + h01 * b.p[k] + h11 * h * b.v[k]) as V3
}

/**
 * Position, velocity and acceleration at time t (measured on the curve).
 * The curve's speed changes smoothly, but its ACCELERATION jumps where one piece meets the next; the body's tilt
 * follows the acceleration, so it is measured over a wider window (about a quarter of a second), which spreads each
 * jump into a smooth change, as a real pilot's body would lag behind the controls.
 */
function motion(keys: Key[], t: number) {
  const e = 1 / 120
  const w = 0.13
  const a = along(keys, t - e)
  const b = along(keys, t)
  const c = along(keys, t + e)
  const before = along(keys, t - w)
  const after = along(keys, t + w)
  const velocity = [0, 1, 2].map((k) => (c[k] - a[k]) / (2 * e)) as V3
  const accel = [0, 1, 2].map((k) => (after[k] - 2 * b[k] + before[k]) / (w * w)) as V3
  return { position: b, velocity, accel }
}

/** Turn smoothly from one facing to another, the short way round. */
function turn(from: number, to: number, p: number): number {
  const d = Math.atan2(Math.sin(to - from), Math.cos(to - from))
  return from + d * smooth(p)
}

/**
 * The pilot's body and engine for one moment of flight, from the path's velocity and acceleration:
 * faces where it flies (or its own way when nearly still), tilts the thrust where the acceleration needs it,
 * and lets its legs trail and its arms hold the pack's handles.
 */
function flight(keys: Key[], t: number, settleYaw: number): ActFrame {
  const { position, velocity, accel } = motion(keys, t)
  const flat = Math.hypot(velocity[0], velocity[2])
  const travelYaw = Math.atan2(velocity[0], velocity[2])
  const yaw = turn(settleYaw, travelYaw, clamp((flat - 0.4) / 1.4))
  // The thrust needed: acceleration plus gravity's pull, as seen by the pilot (forward and sideways).
  const thrust: V3 = [accel[0], accel[1] + G, accel[2]]
  const forward = thrust[0] * Math.sin(yaw) + thrust[2] * Math.cos(yaw)
  const side = thrust[0] * Math.cos(yaw) - thrust[2] * Math.sin(yaw)
  const up = Math.max(1, thrust[1])
  const pitch = clamp(Math.atan2(forward, up), -0.75, 0.75)
  const roll = clamp(-Math.atan2(side, up), -0.6, 0.6)
  const g = Math.hypot(...thrust) / G
  const height = position[1]
  const reach = clamp(1 - height / 0.7) // the legs reach for the ground in the last moments
  const trail = clamp(flat / 6) // legs trail back with speed
  return {
    x: position[0], z: position[2], lift: Math.max(0, height), yaw, pitch, roll, lean: 0.06,
    limbs: {
      lLeg: lerp(0.12 + 0.35 * trail, -0.05, reach), rLeg: lerp(0.2 + 0.4 * trail, 0.0, reach),
      lKnee: lerp(0.45 + 0.2 * trail, 0.15, reach), rKnee: lerp(0.6 + 0.15 * trail, 0.12, reach),
      lLegOut: -0.06 + roll * 0.25, rLegOut: 0.06 + roll * 0.25,
      lArm: -0.35, rArm: -0.35, lArmOut: -0.32, rArmOut: 0.32, lElbow: -1.15, rElbow: -1.15, // hands on the pack's handles
      headX: clamp(0.15 * reach - pitch * 0.4, -0.35, 0.35), // looks down for the ground, keeps eyes level in flight
    },
    prop: { appear: 1, thrust: clamp(g, 0.25, 2.2) },
    velocity,
  }
}

const standing = (over: Partial<ActFrame> = {}): ActFrame => ({
  x: 0, z: 0, lift: 0, yaw: null, pitch: 0, roll: 0, lean: 0, limbs: {}, prop: null, velocity: [0, 0, 0], ...over,
})

// --- Arrival: approach, flare, hover, touchdown, spool-down -----------------------------------------------------

interface Approach {
  delay: number
  /** Where it comes from (off screen) and how fast, then the point over its spot it slows toward. */
  from: V3
  speed: V3
  over: V3
  overSpeed: V3
}

const TOUCHDOWN = 3.7 // seconds from the start of the act to the feet touching the floor
const ARRIVE_LENGTH = 4.9

function arrival({ delay, from, speed, over, overSpeed }: Approach): Act {
  const keys: Key[] = [
    { t: 0, p: from, v: speed },
    { t: 2.3, p: over, v: overSpeed },
    { t: 3.15, p: [0, 0.32, 0], v: [0, -0.42, 0] }, // hovering just above, letting itself down
    { t: TOUCHDOWN, p: [0, 0, 0], v: [0, -0.28, 0] },
  ]
  return {
    delay,
    duration: ARRIVE_LENGTH,
    at(t, faceYaw) {
      if (t < TOUCHDOWN) {
        const frame = flight(keys, t, faceYaw)
        // Over its spot it turns to face the way its place faces.
        frame.yaw = turn(frame.yaw ?? faceYaw, faceYaw, window01(t, 2.2, 3.3))
        return frame
      }
      // Touchdown: the knees take it, the jet cuts out, the pack folds away.
      const k = t - TOUCHDOWN
      const absorb = Math.sin(clamp(k / 0.55) * Math.PI) * (1 - clamp(k / 0.9) * 0.3)
      const settle = window01(k, 0.25, 1.0)
      const thrust = 0.9 * Math.max(0, 1 - k / 0.45) ** 1.5 // spool-down
      return standing({
        lift: -0.04 * absorb, yaw: faceYaw, lean: 0.14 * absorb,
        limbs: {
          lLeg: -0.42 * absorb, rLeg: -0.42 * absorb, lKnee: 0.85 * absorb, rKnee: 0.85 * absorb,
          lArm: lerp(-0.35, 0, settle), rArm: lerp(-0.35, 0, settle),
          lArmOut: lerp(-0.32, -0.12, settle), rArmOut: lerp(0.32, 0.12, settle),
          lElbow: lerp(-1.15, -0.12, settle), rElbow: lerp(-1.15, -0.12, settle),
          headX: 0.15 * (1 - settle),
        },
        prop: { appear: 1 - window01(k, 0.75, 1.15), thrust },
        burst: k < 1 / 30 ? 1 : undefined,
      })
    },
  }
}

// --- Departure: pack unfolds, engine spools up, lift-off, climb away ---------------------------------------------

interface Getaway {
  delay: number
  /** The direction it climbs away in (relative), and the far point off screen it heads for. */
  out: V3
  to: V3
}

const LIFTOFF = 1.35
const LEAVE_LENGTH = 4.8

function departure({ delay, out, to }: Getaway): Act {
  const norm = Math.hypot(out[0], out[2]) || 1
  const dir: V3 = [out[0] / norm, 0, out[2] / norm]
  const keys: Key[] = [
    { t: LIFTOFF, p: [0, 0, 0], v: [0, 0.25, 0] },
    { t: 2.25, p: [dir[0] * 0.15, 0.85, dir[2] * 0.15], v: [dir[0] * 0.7, 1.0, dir[2] * 0.7] }, // straight up off the floor
    { t: 3.2, p: [dir[0] * 1.9, 2.1, dir[2] * 1.9], v: [dir[0] * 3.6, 1.9, dir[2] * 3.6] }, // tips forward, picks up speed
    { t: LEAVE_LENGTH, p: to, v: [(to[0] - dir[0] * 1.9) * 0.9, (to[1] - 2.1) * 0.9, (to[2] - dir[2] * 1.9) * 0.9] },
  ]
  return {
    delay,
    duration: LEAVE_LENGTH,
    at(t, faceYaw) {
      if (t < LIFTOFF) {
        // The pack unfolds; the engine sputters, then catches; the knees load for the jump.
        const appear = window01(t, 0, 0.35)
        const spool = window01(t, 0.45, LIFTOFF)
        const sputter = t < 0.75 ? 0.25 * Math.max(0, Math.sin(t * 60)) : 0
        const load = window01(t, 0.6, LIFTOFF)
        return standing({
          lift: -0.035 * load, yaw: faceYaw, lean: 0.12 * load,
          limbs: {
            lLeg: -0.38 * load, rLeg: -0.38 * load, lKnee: 0.75 * load, rKnee: 0.75 * load,
            lArm: -0.35 * appear, rArm: -0.35 * appear, lArmOut: -0.12 - 0.2 * appear, rArmOut: 0.12 + 0.2 * appear, lElbow: -1.15 * appear, rElbow: -1.15 * appear,
            headX: -0.1 * load,
          },
          prop: { appear, thrust: Math.max(sputter, 0.95 * spool) },
        })
      }
      const frame = flight(keys, t, faceYaw)
      if (t - LIFTOFF < 1 / 30) frame.burst = 0.9
      return frame
    },
  }
}

// --- Each robot's own flight ---------------------------------------------------------------------------------------

const LEFT = -14 // past the left edge of any window (the stage sits toward the right)
const RIGHT = 9.5
const HIGH = 9

export const ARRIVALS: Record<AgentId, Act> = {
  // Straight down from the sky.
  lead: arrival({ delay: 0, from: [0.5, HIGH + 1, -0.6], speed: [-0.1, -6.5, 0.15], over: [0.08, 1.35, 0.02], overSpeed: [0, -1.0, 0] }),
  // From high on the right, sweeping in.
  decider: arrival({ delay: 0.45, from: [RIGHT, 6.5, -2.2], speed: [-6.2, -2.2, 1.2], over: [0.75, 1.3, 0.2], overSpeed: [-0.9, -0.65, -0.1] }),
  // From far left, high, a long glide.
  analyst: arrival({ delay: 0.85, from: [LEFT, 6.5, -1.2], speed: [8.5, -1.6, 0.6], over: [-0.85, 1.35, 0.1], overSpeed: [1.0, -0.6, 0] }),
  // Low and fast from the right, skimming in.
  judge: arrival({ delay: 1.15, from: [RIGHT, 2.6, 1.3], speed: [-7.5, -0.4, -0.6], over: [0.9, 1.1, 0.15], overSpeed: [-1.2, -0.45, -0.1] }),
  // From the far left, low.
  scout: arrival({ delay: 1.45, from: [LEFT, 2.8, 0.6], speed: [9, -0.3, -0.3], over: [-0.9, 1.15, 0.05], overSpeed: [1.2, -0.5, 0] }),
  // From behind, high over the stage, dropping in toward you.
  projects: arrival({ delay: 1.75, from: [0.6, HIGH, -13], speed: [-0.2, -2.4, 7.2], over: [0.05, 1.4, -0.8], overSpeed: [0, -0.7, 0.9] }),
  // From the top left, a steep dive.
  reviewer: arrival({ delay: 2.05, from: [-8, HIGH + 0.5, 0.4], speed: [4.5, -5.5, -0.2], over: [-0.6, 1.4, 0.05], overSpeed: [0.6, -0.8, 0] }),
}

export const DEPARTURES: Record<AgentId, Act> = {
  decider: departure({ delay: 0, out: [1, 0, -0.3], to: [RIGHT + 1, HIGH, -3] }),
  reviewer: departure({ delay: 0.2, out: [-1, 0, 0.1], to: [LEFT, 4.5, 0.8] }),
  projects: departure({ delay: 0.4, out: [0.05, 0, -1], to: [0.6, HIGH, -13] }),
  scout: departure({ delay: 0.6, out: [-1, 0, -0.1], to: [LEFT, 7.5, -1.5] }),
  judge: departure({ delay: 0.8, out: [1, 0, 0.2], to: [RIGHT + 1, 3.5, 1.4] }),
  analyst: departure({ delay: 1.0, out: [-0.8, 0, 0.1], to: [-8, HIGH + 1, 0.5] }),
  lead: departure({ delay: 1.3, out: [0.15, 0, -0.1], to: [0.6, HIGH + 3, -0.8] }),
}

/** When the whole team has finished arriving or leaving, in seconds. */
export function totalTime(acts: Record<AgentId, Act>): number {
  return Math.max(...Object.values(acts).map((a) => a.delay + a.duration))
}
