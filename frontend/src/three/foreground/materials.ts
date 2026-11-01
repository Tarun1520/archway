import { CanvasTexture, MeshStandardMaterial, SRGBColorSpace } from 'three'
import { createRandom } from '../random'

/**
 * The surfaces the furniture is made of.
 *
 * All of them are "standard" materials: they react to light the way real
 * surfaces do. Two numbers describe most of a surface's character:
 *
 *   roughness  0 = mirror-smooth, 1 = completely matte
 *   metalness  0 = not a metal (wood, leather, plastic), 1 = bare metal
 *
 * Each function builds a fresh material; whoever calls it is responsible for
 * disposing it.
 */

/** Polished chrome: the chair's frame and base. It mostly shows reflections of the sky. */
export function createChromeMaterial(): MeshStandardMaterial {
  return new MeshStandardMaterial({ color: '#e6e8ec', roughness: 0.14, metalness: 1 })
}

/** Brushed aluminium: the laptop's body. Metal, but with a soft sheen instead of sharp reflections. */
export function createAluminiumMaterial(): MeshStandardMaterial {
  return new MeshStandardMaterial({ color: '#c9ccd2', roughness: 0.36, metalness: 1 })
}

/** Black powder-coated steel: the desk's frame. */
export function createSteelMaterial(): MeshStandardMaterial {
  return new MeshStandardMaterial({ color: '#17171a', roughness: 0.55, metalness: 0.55 })
}

/** Dark brown leather: the chair's cushions. */
export function createLeatherMaterial(): MeshStandardMaterial {
  return new MeshStandardMaterial({ color: '#3a2a23', roughness: 0.52, metalness: 0 })
}

/** Matte black plastic: casters, arm pads, the screen's frame. */
export function createPlasticMaterial(): MeshStandardMaterial {
  return new MeshStandardMaterial({ color: '#141416', roughness: 0.6, metalness: 0 })
}

/**
 * Pale oak, for the desk top and the drawer unit.
 *
 * The grain is not an image file. It is drawn here, with code, onto an
 * invisible canvas: a base color, then hundreds of thin streaks of slightly
 * lighter and darker brown. three.js then wraps that drawing around the wood.
 *
 */
export function createWoodMaterial(baseColor: string): MeshStandardMaterial {
  const size = 1024
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d')

  if (context) {
    context.fillStyle = baseColor
    context.fillRect(0, 0, size, size)

    // Seeded randomness: the same grain on every visit.
    const random = createRandom(5)
    for (let streak = 0; streak < 900; streak++) {
      const y = random() * size
      const length = size * (0.3 + random() * 0.7)
      const start = random() * size
      const darker = random() < 0.6
      context.strokeStyle = darker ? `rgba(84, 52, 26, ${0.06 + random() * 0.16})` : `rgba(255, 232, 196, ${0.05 + random() * 0.1})`
      context.lineWidth = 0.6 + random() * 2.2
      context.beginPath()
      context.moveTo(start, y)
      // A gentle wobble, so the grain lines are not perfectly straight.
      context.bezierCurveTo(start + length * 0.33, y + (random() - 0.5) * 6, start + length * 0.66, y + (random() - 0.5) * 6, start + length, y)
      context.stroke()
    }
  }

  const grain = new CanvasTexture(canvas)
  grain.colorSpace = SRGBColorSpace // the canvas colors are ordinary screen colors
  grain.anisotropy = 8 // keeps the grain sharp when the desk is seen at a shallow angle

  return new MeshStandardMaterial({ map: grain, roughness: 0.62, metalness: 0 })
}

/** Disposes a material and, if it has one, the texture drawn onto it. */
export function disposeMaterial(material: MeshStandardMaterial): void {
  material.map?.dispose()
  material.dispose()
}
