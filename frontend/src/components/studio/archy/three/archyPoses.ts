import type { ArchyAction } from '../../../../content/archy'
import type { Pose } from '../../agents/three/greetings'

/**
 * What Archy's body does for each action in content/archy.ts, so the robot
 * acts out what it says. A pose is a function of time (seconds since the
 * action began) that returns the joint angles to aim for, in radians, using
 * the same names as the agents' greetings (agents/three/greetings.ts):
 *
 *   rUpX / lUpX    shoulder, forward (negative) and back
 *   rUpZ / lUpZ    shoulder, out to the side (right +, left -)
 *   rLowX / lLowX  elbow bend (negative bends forward)
 *   rLowZ / lLowZ  forearm, side to side (waving)
 *   headX / headY / headZ   nod, turn, tilt
 *   lean / tilt    bow forward / sway sideways, from the hips
 *   lift           a hop, in floor units
 *   spin           an extra turn on the spot
 *
 * `m` is 1 normally and 0 for people who asked for reduced motion: it scales
 * every back-and-forth movement, so the robot still strikes the pose but does
 * not keep moving.
 */

/**
 * A pose, plus what only a floating robot needs: whole-body turns and the legs.
 *
 *   flip     turn head over heels (about his middle), radians; 2 pi is one full flip
 *   roll     turn sideways, like a cartwheel in the air
 *   dive     0 upright, 1 flat and belly-down, turned so he is seen from above and behind (the skydiver)
 *   lLegX / rLegX    thigh, forward (negative) and back
 *   lKneeX / rKneeX  knee bend (positive bends the shin back)
 *   splay    both legs out to the sides
 *   rise     extra height above his normal float, in world units
 */
export interface ArchyBody extends Pose {
  flip?: number
  roll?: number
  dive?: number
  lLegX?: number
  rLegX?: number
  lKneeX?: number
  rKneeX?: number
  splay?: number
  rise?: number
}

export type ArchyPose = (t: number, m: number) => ArchyBody

const wobble = (t: number, speed: number, size: number, m: number, shift = 0) => Math.sin(t * speed + shift) * size * m

export const ARCHY_POSES: Record<ArchyAction, ArchyPose> = {
  // Coming out of the portal: arms a little out, looking up into the light.
  rise: (t, m) => ({ rUpZ: 0.55, lUpZ: -0.55, headX: -0.28, headY: wobble(t, 1.5, 0.12, m) }),

  // Waiting: breathing, now and then a glance to one side.
  idle: (t, m) => ({ headY: wobble(t, 0.7, 0.28, m), headZ: wobble(t, 0.45, 0.05, m) }),

  // "Hi!": the right arm high, the forearm waving, the head tilted.
  wave: (t, m) => ({ rUpZ: 2.55, rLowZ: wobble(t, 11, 0.55, m), headZ: -0.14, headY: 0.1, tilt: wobble(t, 11, 0.02, m) }),

  // "Tell me out loud": the right arm reaches out toward the person, a little to the side
  // so it can be seen from the front, with small jabs.
  point: (t, m) => ({
    rUpX: -1.2 + wobble(t, 4, 0.1, m),
    rUpZ: 0.75,
    rLowX: -0.15,
    lUpZ: -0.3,
    lean: 0.12,
    headX: 0.06,
    headY: -0.12,
  }),

  // Explaining: both hands open and moving in turns, the head following the words.
  explain: (t, m) => ({
    rUpX: -0.8 + wobble(t, 2.3, 0.3, m),
    rUpZ: 0.55 + wobble(t, 2.3, 0.14, m, 1),
    rLowX: -1.0 + wobble(t, 2.3, 0.35, m, 1.2),
    lUpX: -0.8 + wobble(t, 2.3, 0.3, m, Math.PI),
    lUpZ: -0.55 + wobble(t, 2.3, 0.14, m, Math.PI + 1),
    lLowX: -1.0 + wobble(t, 2.3, 0.35, m, Math.PI + 1.2),
    headY: wobble(t, 1.1, 0.2, m),
    headX: wobble(t, 2.3, 0.05, m),
  }),

  // Listening: a hand cupped to the ear, the head tilted toward it, leaning in.
  listen: (t, m) => ({
    lUpX: -0.35,
    lUpZ: -2.5,
    lLowX: -0.2,
    lLowZ: 1.75,
    headZ: 0.2,
    headY: 0.12,
    lean: 0.1 + wobble(t, 2.2, 0.015, m),
    rUpZ: 0.14,
  }),

  // A question: palms up, a small shrug, the head tilted.
  ask: (t, m) => ({
    rUpX: -0.85,
    lUpX: -0.85,
    rUpZ: 0.7,
    lUpZ: -0.7,
    rLowX: -1.05,
    lLowX: -1.05,
    headZ: 0.2,
    lean: 0.08,
    tilt: wobble(t, 2.4, 0.04, m),
  }),

  // Thinking: a hand on the chin, eyes up and away, the head slowly turning.
  think: (t, m) => ({
    rUpX: -0.75,
    rUpZ: -0.3,
    rLowX: -2.25,
    lUpZ: -0.15,
    headX: -0.18,
    headY: 0.35 + wobble(t, 0.9, 0.25, m),
    tilt: 0.04,
  }),

  // "Great!": nods, and a small thumbs-up posture with the right arm.
  nod: (t, m) => ({
    headX: m ? 0.3 * Math.max(0, Math.sin(t * 7)) : 0.15,
    rUpX: -0.9,
    rLowX: -1.2,
    rUpZ: 0.25,
    lean: 0.05,
  }),

  // Done: a backflip in the air, then both arms up and waving.
  celebrate: (t, m) => {
    const turn = m ? Math.min(1, t / 1.2) : 0
    const eased = turn * turn * (3 - 2 * turn)
    const tucked = turn > 0.15 && turn < 0.85
    return {
      flip: -eased * 2 * Math.PI,
      rise: m ? Math.sin(turn * Math.PI) * 0.35 : 0,
      rUpZ: tucked ? 0.5 : 2.6,
      lUpZ: tucked ? -0.5 : -2.6,
      rUpX: tucked ? -1.3 : 0,
      lUpX: tucked ? -1.3 : 0,
      rLowX: tucked ? -1.6 : -0.12,
      lLowX: tucked ? -1.6 : -0.12,
      lLegX: tucked ? -1.3 : undefined,
      rLegX: tucked ? -1.3 : undefined,
      lKneeX: tucked ? 1.6 : undefined,
      rKneeX: tucked ? 1.6 : undefined,
      rLowZ: turn >= 1 ? wobble(t, 13, 0.4, m) : 0,
      lLowZ: turn >= 1 ? wobble(t, 13, -0.4, m) : 0,
      headX: -0.18,
    }
  },
}


/**
 * The tricks he tries when he has nothing to say: he floats on a column of
 * rising air, and now and then plays in it. Each is a pose over time; `d` is
 * how long it lasts, in seconds. They are only played while he is not
 * speaking and nobody else is (see archyStage.ts).
 */
export type TrickName = 'skydive' | 'flip' | 'roll' | 'spin' | 'swim' | 'flail'

export interface Trick {
  duration: number
  pose: (t: number, m: number, d: number) => ArchyBody
}

/** 0 up to 1 and back to 0 over the trick, with soft edges. */
const hump = (t: number, d: number, edge = 0.3) => {
  const k = Math.max(0, Math.min(1, t / edge, (d - t) / edge))
  return k * k * (3 - 2 * k)
}

export const TRICKS: Record<TrickName, Trick> = {
  // Skydiving: flat on his belly, seen from the side in the classic arch: arms up and bent forward
  // like goalposts, legs bent up behind, drifting in the wind.
  skydive: {
    duration: 3.2,
    pose: (t, m, d) => {
      const k = hump(t, d, 0.5)
      return {
        dive: k,
        rUpX: (1.55 + wobble(t, 7, 0.1, m)) * k,
        lUpX: (1.55 + wobble(t, 7, -0.1, m)) * k,
        rUpZ: 0.4 * k,
        lUpZ: -0.4 * k,
        rLowX: 1.4 * k,
        lLowX: 1.4 * k,
        lLegX: 0.55 * k,
        rLegX: 0.55 * k,
        lKneeX: 1.0 * k,
        rKneeX: 1.0 * k,
        splay: 0.3 * k,
        headX: -0.55 * k,
        rise: 0.05 * k,
        tilt: wobble(t, 3.2, 0.05, m),
      }
    },
  },

  // An air flip: tucks into a ball and does a full backflip about his middle.
  flip: {
    duration: 1.5,
    pose: (t, m, d) => {
      const turn = Math.min(1, t / (d * 0.85))
      const eased = turn * turn * (3 - 2 * turn)
      const tuck = Math.sin(turn * Math.PI) > 0.35 ? 1 : 0
      return {
        flip: -eased * 2 * Math.PI * m,
        rise: Math.sin(turn * Math.PI) * 0.4 * m,
        rUpX: -1.3 * tuck,
        lUpX: -1.3 * tuck,
        rLowX: -1.7 * tuck,
        lLowX: -1.7 * tuck,
        rUpZ: tuck ? 0.4 : 0.9,
        lUpZ: tuck ? -0.4 : -0.9,
        lLegX: tuck ? -1.4 : 0,
        rLegX: tuck ? -1.4 : 0,
        lKneeX: tuck ? 1.7 : 0,
        rKneeX: tuck ? 1.7 : 0,
      }
    },
  },

  // A sideways roll, like a cartwheel in the air, arms out.
  roll: {
    duration: 1.7,
    pose: (t, m, d) => {
      const turn = Math.min(1, t / (d * 0.85))
      const eased = turn * turn * (3 - 2 * turn)
      return { roll: eased * 2 * Math.PI * m, rise: Math.sin(turn * Math.PI) * 0.25 * m, rUpZ: 1.5, lUpZ: -1.5, splay: 0.35 }
    },
  },

  // A pirouette, arms out, legs together.
  spin: {
    duration: 1.8,
    pose: (t, m, d) => {
      const turn = Math.min(1, t / (d * 0.9))
      const eased = turn * turn * (3 - 2 * turn)
      return { spin: eased * 4 * Math.PI * m, rUpZ: 1.3, lUpZ: -1.3, rLowZ: 0.3, lLowZ: -0.3, headX: 0.1 }
    },
  },

  // Swimming in the air: leaning into it, arms circling like freestyle, legs kicking.
  swim: {
    duration: 3.2,
    pose: (t, m, d) => {
      const k = hump(t, d, 0.4)
      const stroke = t * 6.5 * m
      return {
        lean: 0.55 * k,
        rUpX: Math.sin(stroke) * 1.6 * k - 1.2 * k,
        lUpX: Math.sin(stroke + Math.PI) * 1.6 * k - 1.2 * k,
        rUpZ: 0.5 * k,
        lUpZ: -0.5 * k,
        rLowX: -0.5,
        lLowX: -0.5,
        lLegX: wobble(t, 13, 0.5, m) * k,
        rLegX: wobble(t, 13, -0.5, m) * k,
        lKneeX: 0.3 + Math.max(0, wobble(t, 13, 0.5, m)) * k,
        rKneeX: 0.3 + Math.max(0, wobble(t, 13, -0.5, m)) * k,
        headX: -0.25 * k,
        rise: 0.08 * k,
      }
    },
  },

  // A gust catches him: arms and legs flail, the whole body wobbles.
  flail: {
    duration: 2.2,
    pose: (t, m, d) => {
      const k = hump(t, d, 0.25)
      return {
        rUpZ: (1.4 + wobble(t, 17, 0.9, m)) * k,
        lUpZ: (-1.4 + wobble(t, 15, 0.9, m, 1)) * k,
        rUpX: wobble(t, 12, 1.0, m) * k,
        lUpX: wobble(t, 11, 1.0, m, 2) * k,
        rLowX: -0.6,
        lLowX: -0.6,
        lLegX: wobble(t, 14, 0.7, m) * k,
        rLegX: wobble(t, 13, 0.7, m, 1) * k,
        lKneeX: 0.5 + wobble(t, 14, 0.4, m) * k,
        rKneeX: 0.5 + wobble(t, 13, 0.4, m, 1) * k,
        roll: wobble(t, 6, 0.45, m) * k,
        tilt: wobble(t, 9, 0.12, m) * k,
        headZ: wobble(t, 8, 0.3, m) * k,
        rise: 0.06 * k,
      }
    },
  },
}

export const TRICK_NAMES = Object.keys(TRICKS) as TrickName[]
