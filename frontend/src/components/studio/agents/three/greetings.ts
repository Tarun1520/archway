import type { AgentId } from '../../../../lib/agentTeam'

/**
 * How each robot says hello when the pointer rests on it: a short, funny move
 * of its own, plus a line in a speech bubble.
 *
 * A move is a function of time (seconds since it began) that returns the
 * joint angles to aim for, in radians. Anything it leaves out keeps the
 * robot's normal pose, so a move only describes what it changes.
 *
 *   rUpX / lUpX   right / left shoulder, forward (negative) and back
 *   rUpZ / lUpZ   right / left shoulder, out to the side (right +, left -)
 *   rLowX / lLowX right / left elbow bend (negative bends forward)
 *   rLowZ / lLowZ right / left forearm, side to side (for waving)
 *   headX / headY / headZ   nod, turn, tilt
 *   lean / tilt   bow forward / sway sideways, from the hips
 *   lift          a hop, in floor units
 *   spin          an extra turn on the spot
 */
export interface Pose {
  rUpX?: number
  rUpZ?: number
  rLowX?: number
  rLowZ?: number
  lUpX?: number
  lUpZ?: number
  lLowX?: number
  lLowZ?: number
  headX?: number
  headY?: number
  headZ?: number
  lean?: number
  tilt?: number
  lift?: number
  spin?: number
}

export interface Greeting {
  /** How long the move lasts, in seconds. */
  duration: number
  /** What the robot says. */
  line: string
  pose: (t: number, duration: number) => Pose
}

/** 0 → 1 → 0 over the move, smooth at both ends: for moves that go out and come back. */
function inOut(t: number, duration: number, edge = 0.25): number {
  const up = Math.min(1, t / edge)
  const down = Math.min(1, (duration - t) / edge)
  const k = Math.max(0, Math.min(up, down))
  return k * k * (3 - 2 * k)
}

export const GREETINGS: Record<AgentId, Greeting> = {
  // The lead: a crisp salute, then a proud little nod.
  lead: {
    duration: 1.9,
    line: 'At your service! I decide who works next.',
    pose: (t, d) => {
      const k = inOut(t, d)
      return { rUpX: -1.1 * k, rUpZ: 1.05 * k, rLowX: -2.1 * k, headX: t > 0.9 && t < 1.4 ? 0.25 * Math.sin((t - 0.9) * 2 * Math.PI) : 0, lift: 0.01 * k }
    },
  },
  // The analyst: a big, keen wave.
  analyst: {
    duration: 1.8,
    line: 'Hello! I split your idea into its parts.',
    pose: (t, d) => {
      const k = inOut(t, d)
      return { rUpZ: 2.6 * k, rLowZ: Math.sin(t * 14) * 0.55 * k, headZ: -0.18 * k, tilt: -0.06 * k }
    },
  },
  // The scout: two excited hops, arms up, and a spin on the second.
  scout: {
    duration: 1.6,
    line: 'Hey hey! I go and find the open-source pieces!',
    pose: (t, d) => {
      const k = inOut(t, d, 0.15)
      const hop = Math.abs(Math.sin((t / d) * 2 * Math.PI))
      return { lift: hop * 0.16 * k, rUpZ: 2.5 * k, lUpZ: -2.5 * k, rLowZ: 0.3 * k, lLowZ: -0.3 * k, spin: t > d / 2 ? ((t - d / 2) / (d / 2)) * 2 * Math.PI : 0 }
    },
  },
  // The judge: leans in to inspect you, squints left and right, then nods: approved.
  judge: {
    duration: 2.2,
    line: 'Hmm… let me see. Yes. You are relevant.',
    pose: (t, d) => {
      const k = inOut(t, d)
      const inspecting = t < 1.4
      return {
        lean: 0.28 * k,
        headY: inspecting ? Math.sin(t * 4.5) * 0.45 * k : 0,
        headX: inspecting ? 0.15 * k : Math.sin((t - 1.4) * 14) * 0.22 * k,
        rUpX: -0.5 * k,
        rLowX: -1.6 * k, // a hand on the chin
        rUpZ: -0.25 * k,
      }
    },
  },
  // The project scout: a little dance, hips swaying, arms taking turns.
  projects: {
    duration: 2,
    line: 'Apps like yours? Let me show you my moves first!',
    pose: (t, d) => {
      const k = inOut(t, d)
      const beat = Math.sin(t * 9)
      return {
        tilt: beat * 0.14 * k,
        rUpZ: (1.6 + beat * 0.9) * k,
        lUpZ: (-1.6 + beat * 0.9) * k,
        rLowX: -0.6 * k,
        lLowX: -0.6 * k,
        headZ: -beat * 0.2 * k,
        lift: Math.abs(Math.sin(t * 9)) * 0.03 * k,
      }
    },
  },
  // The reviewer: peekaboo! Hands up by its face, head ducked, then arms thrown wide.
  reviewer: {
    duration: 2,
    line: 'Peekaboo! I spot what everyone else missed.',
    pose: (t, d) => {
      const k = inOut(t, d, 0.2)
      const hiding = t < 0.95
      return hiding
        ? { rUpX: -1.15 * k, lUpX: -1.15 * k, rUpZ: 0.95 * k, lUpZ: -0.95 * k, rLowX: -2.2 * k, lLowX: -2.2 * k, headX: 0.3 * k } // hands up by the face, head ducked
        : { rUpZ: 1.9 * k, lUpZ: -1.9 * k, rLowZ: 0.4 * k, lLowZ: -0.4 * k, lift: 0.05 * Math.max(0, Math.sin((t - 0.95) * 6)) * k, headX: -0.15 * k }
    },
  },
  // Laya, the decider: an elegant, slightly overdone bow.
  decider: {
    duration: 2.1,
    line: 'Laya, delighted. I weigh fit, risk and review.',
    pose: (t, d) => {
      const k = inOut(t, d, 0.45)
      return { lean: 0.62 * k, rUpX: -0.55 * k, rUpZ: -0.35 * k, rLowX: -1.5 * k, lUpX: 0.6 * k, lUpZ: -0.2 * k, headX: 0.2 * k }
    },
  },
}
