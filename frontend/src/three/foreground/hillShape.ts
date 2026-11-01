/**
 * The shape of the foreground hill, as one function: give it a position on
 * the ground (x, z) and it returns the height of the hill there, in metres.
 *
 * The ground mesh, the grass and the flowers all ask this same function,
 * which is what keeps them sitting on the same surface.
 *
 * The middle of the hilltop (around the origin) is flat, so the furniture
 * stands level. Away from it the ground becomes uneven and falls away.
 */

/** Blends smoothly from 0 to 1 as `value` goes from `start` to `end`. */
function smoothstep(start: number, end: number, value: number): number {
  const t = Math.min(Math.max((value - start) / (end - start), 0), 1)
  return t * t * (3 - 2 * t)
}

export function hillHeight(x: number, z: number): number {
  // The hill falls away to the left and right.
  const sideFall = -0.02 * x * x

  let frontOrBack: number
  if (z > 0) {
    // In front of the desk (toward the viewer) it slopes down.
    frontOrBack = -(0.1 * z + 0.03 * z * z)
  } else if (z > -5) {
    // Behind the desk it rises gently, so grass shows behind the furniture.
    frontOrBack = 0.07 * -z
  } else {
    // Farther back it drops out of sight.
    const past = -z - 5
    frontOrBack = 0.35 - 0.3 * past * past
  }

  // Two overlapping waves make the surface uneven instead of perfectly smooth.
  const bumps = 0.07 * Math.sin(x * 0.9 + 1.3) * Math.cos(z * 0.7) + 0.04 * Math.sin(x * 2.3 + z * 1.7)

  // 0 on the flat hilltop under the furniture, 1 out on the open hill.
  const awayFromTop = smoothstep(1.3, 3.6, Math.hypot(x, z))

  return awayFromTop * (sideFall + frontOrBack + bumps)
}
