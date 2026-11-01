/**
 * The jetpack every robot flies in and out on, and what it puts out: flames, light, smoke and dust.
 *
 *   jetpack   a back plate with two rounded tanks, an engine block between them, two bell nozzles and shoulder
 *             straps. Under each nozzle a layered flame (white-hot core, orange body, faint outer plume, and bright
 *             "shock diamonds" at full power) and a wide glow at the nozzle.
 *             The flame's length and flicker follow the thrust.
 *   smoke     a pool of soft puffs in the world (not attached to anyone):
 *               exhaust  leaves each nozzle along the jet, carries some of the flyer's own speed (so it trails
 *                        behind), warm for an instant near the flame, then grey; it slows in the air, swirls, grows
 *                        and fades
 *               dust     when the jet is close to the floor it hits the ground and rolls outward in a ring (ground
 *                        effect); a touchdown or a lift-off throws a burst of it
 *   glow      a warm patch of light on the floor under a robot whose jet is close to the ground
 *
 * The jetpack grows in before take-off and folds away after landing, so nothing pops.
 */
import {
  AdditiveBlending,
  BoxGeometry,
  CanvasTexture,
  CapsuleGeometry,
  DynamicDrawUsage,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  Color,
  ConeGeometry,
  Group,
  LatheGeometry,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PlaneGeometry,
  Quaternion,
  SRGBColorSpace,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  Sprite,
  SpriteMaterial,
  TorusGeometry,
  Vector2,
  Vector3,
} from 'three'
import type { RobotRig } from './buildRobot'
import { HIP } from './buildRobot'

/** What a move says about the jetpack in one frame. */
export interface PropFrame {
  /** 0 hidden, 1 fully there (grows in and folds away between). */
  appear: number
  /** 0 off, 1 hovering, up to about 2 when braking hard. */
  thrust?: number
}

export function softTexture(): CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 64
  const context = canvas.getContext('2d')!
  const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32)
  gradient.addColorStop(0, 'rgba(255,255,255,0.95)')
  gradient.addColorStop(0.4, 'rgba(255,255,255,0.5)')
  gradient.addColorStop(1, 'rgba(255,255,255,0)')
  context.fillStyle = gradient
  context.fillRect(0, 0, 64, 64)
  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  return texture
}

export interface Jetpack {
  update(frame: PropFrame | null, dt: number, time: number): void
  /** Where the exhaust leaves (world positions) and which way it goes (world direction, unit). */
  exhaust(): { points: Vector3[]; direction: Vector3 }
  dispose(): void
}

/** A bell-shaped nozzle, turned on a lathe. */
function bell(): LatheGeometry {
  const profile = [
    new Vector2(0.018, 0.03), new Vector2(0.02, 0.012), new Vector2(0.026, -0.005), new Vector2(0.034, -0.022), new Vector2(0.04, -0.035),
  ]
  return new LatheGeometry(profile, 20)
}

export function createJetpack(rig: RobotRig, accent: Color, texture: CanvasTexture): Jetpack {
  const owned: { dispose(): void }[] = []
  const keep = <T extends { dispose(): void }>(item: T) => (owned.push(item), item)
  const metal = keep(new MeshStandardMaterial({ color: '#aeb6bf', roughness: 0.28, metalness: 0.85 }))
  const dark = keep(new MeshStandardMaterial({ color: '#23252a', roughness: 0.55, metalness: 0.3 }))
  const strapMaterial = keep(new MeshStandardMaterial({ color: '#2d3036', roughness: 0.8 }))
  const trim = keep(new MeshBasicMaterial({ color: accent, toneMapped: false }))

  const pack = new Group()
  pack.position.set(0, 0.45 - HIP + 0.03, -0.165)
  pack.visible = false
  rig.body.add(pack)

  const plate = new Mesh(keep(new BoxGeometry(0.2, 0.25, 0.03)), dark)
  plate.position.z = 0.035
  pack.add(plate)
  const engine = new Mesh(keep(new BoxGeometry(0.075, 0.13, 0.07)), dark)
  engine.position.set(0, -0.02, -0.02)
  pack.add(engine)
  const stripe = new Mesh(keep(new BoxGeometry(0.077, 0.012, 0.072)), trim)
  stripe.position.set(0, 0.03, -0.02)
  pack.add(stripe)

  const tips: Group[] = []
  const flames: Group[] = []
  const diamonds: Mesh[] = []
  const glows: Sprite[] = []
  const coreMaterial = keep(new MeshBasicMaterial({ color: '#fff6d8', transparent: true, opacity: 0.95, blending: AdditiveBlending, depthWrite: false, toneMapped: false }))
  const bodyMaterial = keep(new MeshBasicMaterial({ color: '#ff8a22', transparent: true, opacity: 0.8, blending: AdditiveBlending, depthWrite: false, toneMapped: false }))
  const plumeMaterial = keep(new MeshBasicMaterial({ color: '#ff4a1a', transparent: true, opacity: 0.3, blending: AdditiveBlending, depthWrite: false, toneMapped: false }))
  const diamondMaterial = keep(new MeshBasicMaterial({ color: '#ffe9b0', transparent: true, opacity: 0.85, blending: AdditiveBlending, depthWrite: false, toneMapped: false }))
  // A wide glow: from the front the legs hide the nozzles, and the light spills round them.
  const glowMaterial = keep(new SpriteMaterial({ map: texture, color: '#ffb066', transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false }))
  const coreGeometry = keep(new ConeGeometry(0.016, 1, 12, 1, true))
  const bodyGeometry = keep(new ConeGeometry(0.03, 1, 14, 1, true))
  const plumeGeometry = keep(new ConeGeometry(0.05, 1, 14, 1, true))
  const diamondGeometry = keep(new SphereGeometry(0.012, 8, 6))

  for (const side of [-1, 1]) {
    const tank = new Mesh(keep(new CapsuleGeometry(0.048, 0.15, 6, 18)), metal)
    tank.position.set(side * 0.066, 0.005, -0.025)
    pack.add(tank)
    const band = new Mesh(keep(new TorusGeometry(0.049, 0.006, 6, 20)), dark)
    band.rotation.x = Math.PI / 2
    band.position.set(side * 0.066, 0.045, -0.025)
    pack.add(band)
    const nozzle = new Mesh(keep(bell()), dark)
    nozzle.position.set(side * 0.066, -0.14, -0.025)
    pack.add(nozzle)

    // Shoulder strap: an arch from the back plate over the shoulder to the chest.
    const strap = new Mesh(keep(new TorusGeometry(0.135, 0.011, 6, 24, Math.PI)), strapMaterial)
    strap.rotation.y = Math.PI / 2
    strap.position.set(side * 0.115, -0.005, 0.165)
    pack.add(strap)

    const tip = new Group()
    tip.position.set(side * 0.066, -0.178, -0.025)
    pack.add(tip)
    tips.push(tip)

    const flame = new Group()
    for (const [geometry, material] of [[plumeGeometry, plumeMaterial], [bodyGeometry, bodyMaterial], [coreGeometry, coreMaterial]] as const) {
      const cone = new Mesh(geometry, material)
      cone.rotation.x = Math.PI // pointing down
      cone.position.y = -0.5 // the cone is one unit long; the flame group scales it
      flame.add(cone)
    }
    tip.add(flame)
    flames.push(flame)
    for (let index = 1; index <= 3; index++) {
      const diamond = new Mesh(diamondGeometry, diamondMaterial)
      tip.add(diamond)
      diamonds.push(diamond)
    }
    const glow = new Sprite(glowMaterial)
    glow.scale.set(0.16, 0.16, 1)
    tip.add(glow)
    glows.push(glow)
  }

  const down = new Vector3()
  const turn = new Quaternion()
  return {
    update(frame, _dt, time) {
      const appear = frame?.appear ?? 0
      pack.visible = appear > 0.001
      pack.scale.setScalar(Math.max(0.001, appear < 1 ? appear * (1 + 0.12 * Math.sin(appear * Math.PI)) : 1))
      const thrust = frame ? Math.max(0, frame.thrust ?? 0) : 0
      flames.forEach((flame, index) => {
        // Turbulent flicker: two fast sines and a slower wander, different for each nozzle.
        const flicker = 0.86 + 0.09 * Math.sin(time * 53 + index * 1.7) + 0.05 * Math.sin(time * 31 + index * 4.1)
        const length = thrust > 0.02 ? (0.12 + 0.26 * thrust) * flicker : 0
        flame.visible = length > 0.005
        flame.scale.set(0.75 + 0.35 * Math.min(1.4, thrust), length, 0.75 + 0.35 * Math.min(1.4, thrust))
      })
      // Shock diamonds: bright knots in the jet, only at high power.
      const strong = Math.max(0, thrust - 0.75) / 0.6
      diamonds.forEach((diamond, index) => {
        const order = (index % 3) + 1
        diamond.visible = strong > 0.05
        diamond.position.y = -(0.035 + 0.045 * order) * (0.7 + 0.5 * Math.min(1.5, thrust))
        diamond.scale.setScalar(Math.max(0.001, strong * (1.1 - order * 0.22) * (0.85 + 0.15 * Math.sin(time * 40 + index))))
      })
      glowMaterial.opacity = Math.min(0.75, thrust * 0.45)
      for (const glow of glows) glow.scale.setScalar(0.22 + 0.26 * Math.min(1.5, thrust))
    },
    exhaust() {
      pack.getWorldQuaternion(turn)
      down.set(0, -1, 0).applyQuaternion(turn).normalize()
      return { points: tips.map((tip) => tip.getWorldPosition(new Vector3())), direction: down.clone() }
    },
    dispose() {
      pack.removeFromParent()
      for (const item of owned) item.dispose()
    },
  }
}

// --- The warm patch on the floor under a low jet -----------------------------------------------------------

export function createGroundGlow(texture: CanvasTexture): { mesh: Mesh; set(x: number, z: number, level: number): void; dispose(): void } {
  const geometry = new PlaneGeometry(1.1, 1.1)
  const material = new MeshBasicMaterial({ map: texture, color: '#ff9440', transparent: true, opacity: 0, blending: AdditiveBlending, depthWrite: false, toneMapped: false })
  const mesh = new Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.visible = false
  return {
    mesh,
    set(x, z, level) {
      mesh.visible = level > 0.01
      mesh.position.set(x, 0.006, z)
      material.opacity = Math.min(0.75, level)
      mesh.scale.setScalar(0.6 + 0.6 * level)
    },
    dispose() {
      geometry.dispose()
      material.dispose()
    },
  }
}

// --- Smoke and dust -------------------------------------------------------------------------------------------

/**
 * All the puffs are drawn in ONE draw call: one flat square, repeated once per puff ("instancing"), each copy given
 * its own place, size, colour and opacity, and turned to face the camera in the shader. (One sprite per puff would be
 * hundreds of separate draws a frame, which made the flights stutter.)
 */
const SMOKE_VERTEX = `
  attribute vec3 offset;
  attribute float size;
  attribute float alpha;
  attribute vec3 tint;
  varying vec2 vUv;
  varying float vAlpha;
  varying vec3 vTint;
  #include <clipping_planes_pars_vertex>
  void main() {
    vUv = uv;
    vAlpha = alpha;
    vTint = tint;
    vec4 mvPosition = modelViewMatrix * vec4(offset, 1.0);
    mvPosition.xy += position.xy * size; // face the camera
    gl_Position = projectionMatrix * mvPosition;
    #include <clipping_planes_vertex>
  }
`
const SMOKE_FRAGMENT = `
  uniform sampler2D map;
  varying vec2 vUv;
  varying float vAlpha;
  varying vec3 vTint;
  #include <clipping_planes_pars_fragment>
  void main() {
    #include <clipping_planes_fragment>
    vec4 texel = texture2D(map, vUv);
    float a = texel.a * vAlpha;
    if (a < 0.003) discard;
    gl_FragColor = vec4(vTint, a);
  }
`

interface Puff {
  position: Vector3
  velocity: Vector3
  age: number
  life: number
  size: number
  grow: number
  opacity: number
  swirl: number
  alive: boolean
  kind: 'exhaust' | 'dust'
}

export interface Smoke {
  /** The one mesh that draws every puff. */
  mesh: Mesh
  /** Exhaust out of each point, along `direction` at `speed`, carrying `carry` of the flyer's velocity. */
  exhaust(points: Vector3[], direction: Vector3, speed: number, rate: number, carry: Vector3, dt: number): void
  /** Dust rolling outward over the floor around (x, z): the jet hitting the ground. */
  groundRing(x: number, z: number, strength: number, dt: number): void
  /** A burst of dust (touchdown, lift-off). */
  burst(x: number, z: number, strength: number): void
  /** Moves every puff; returns true while any is still in the air. */
  update(dt: number): boolean
  dispose(): void
}

const EXHAUST = new Color('#d6d9de')
const WARM = new Color('#ffc890')
const DUST = new Color('#a39b90')

export function createSmoke(scene: Scene, texture: CanvasTexture, capacity = 420): Smoke {
  const quad = new PlaneGeometry(1, 1)
  const geometry = new InstancedBufferGeometry()
  geometry.index = quad.index
  geometry.setAttribute('position', quad.getAttribute('position'))
  geometry.setAttribute('uv', quad.getAttribute('uv'))
  const offsets = new InstancedBufferAttribute(new Float32Array(capacity * 3), 3)
  const sizes = new InstancedBufferAttribute(new Float32Array(capacity), 1)
  const alphas = new InstancedBufferAttribute(new Float32Array(capacity), 1)
  const tints = new InstancedBufferAttribute(new Float32Array(capacity * 3), 3)
  for (const attribute of [offsets, sizes, alphas, tints]) attribute.setUsage(DynamicDrawUsage)
  geometry.setAttribute('offset', offsets)
  geometry.setAttribute('size', sizes)
  geometry.setAttribute('alpha', alphas)
  geometry.setAttribute('tint', tints)
  geometry.instanceCount = capacity
  const material = new ShaderMaterial({
    uniforms: { map: { value: texture } },
    vertexShader: SMOKE_VERTEX,
    fragmentShader: SMOKE_FRAGMENT,
    transparent: true,
    depthWrite: false,
    clipping: true, // obeys the stage's "nothing below the floor"
  })
  const mesh = new Mesh(geometry, material)
  mesh.frustumCulled = false // the puffs are everywhere; their box is not the quad's
  mesh.renderOrder = 2 // after the robots, so they show through it correctly
  scene.add(mesh)

  const puffs: Puff[] = Array.from({ length: capacity }, () => ({
    position: new Vector3(), velocity: new Vector3(), age: 0, life: 1, size: 0.1, grow: 0.5, opacity: 0.5, swirl: 0, alive: false, kind: 'exhaust' as const,
  }))
  let next = 0
  const owed = new Map<string, number>()
  let seed = 11
  const random = () => {
    seed = (seed * 16807) % 2147483647
    return seed / 2147483647
  }
  const spawn = (): Puff | null => {
    for (let tries = 0; tries < capacity; tries++) {
      const puff = puffs[next]
      next = (next + 1) % capacity
      if (!puff.alive) return puff
    }
    return null
  }
  const due = (key: string, rate: number, dt: number) => {
    let count = (owed.get(key) ?? 0) + rate * dt
    const whole = Math.floor(count)
    count -= whole
    owed.set(key, count)
    return whole
  }
  const start = (puff: Puff, kind: Puff['kind'], at: Vector3, velocity: Vector3, life: number, size: number, grow: number, opacity: number) => {
    puff.alive = true
    puff.kind = kind
    puff.age = 0
    puff.life = life
    puff.size = size
    puff.grow = grow
    puff.opacity = opacity
    puff.swirl = random() * Math.PI * 2
    puff.position.copy(at)
    puff.velocity.copy(velocity)
  }
  const colour = new Color()
  const jitter = new Vector3()

  return {
    mesh,
    exhaust(points, direction, speed, rate, carry, dt) {
      points.forEach((point, index) => {
        const count = due(`e${index}`, rate, dt)
        for (let n = 0; n < count; n++) {
          const puff = spawn()
          if (!puff) return
          jitter.set(random() - 0.5, random() - 0.5, random() - 0.5).multiplyScalar(0.5)
          const velocity = direction.clone().multiplyScalar(speed * (0.75 + random() * 0.5)).add(jitter).addScaledVector(carry, 0.55)
          // Born a little way down the jet, where the flame ends.
          const at = point.clone().addScaledVector(direction, 0.06 + random() * 0.1)
          start(puff, 'exhaust', at, velocity, 0.8 + random() * 0.9, 0.05 + random() * 0.04, 0.45 + random() * 0.3, 0.32)
        }
      })
    },
    groundRing(x, z, strength, dt) {
      const count = due('ground', 28 * strength, dt)
      for (let n = 0; n < count; n++) {
        const puff = spawn()
        if (!puff) return
        const angle = random() * Math.PI * 2
        const speed = (0.9 + random() * 1.1) * (0.5 + strength)
        start(puff, 'dust', new Vector3(x + Math.cos(angle) * 0.08, 0.04, z + Math.sin(angle) * 0.08),
          new Vector3(Math.cos(angle) * speed, 0.05 + random() * 0.15, Math.sin(angle) * speed), 1.1 + random() * 0.9, 0.06 + random() * 0.05, 0.5 + random() * 0.35, 0.26)
      }
    },
    burst(x, z, strength) {
      const count = Math.round(26 * strength)
      for (let n = 0; n < count; n++) {
        const puff = spawn()
        if (!puff) return
        const angle = (n / count) * Math.PI * 2 + random() * 0.3
        const speed = (1.6 + random() * 1.2) * strength
        start(puff, 'dust', new Vector3(x + Math.cos(angle) * 0.1, 0.05, z + Math.sin(angle) * 0.1),
          new Vector3(Math.cos(angle) * speed, 0.1 + random() * 0.25, Math.sin(angle) * speed), 1.3 + random() * 0.9, 0.08 + random() * 0.05, 0.6 + random() * 0.35, 0.32)
      }
    },
    update(dt) {
      let any = false
      puffs.forEach((puff, index) => {
        if (puff.alive) {
          puff.age += dt
          if (puff.age >= puff.life) puff.alive = false
        }
        if (!puff.alive) {
          alphas.setX(index, 0)
          sizes.setX(index, 0)
          return
        }
        any = true
        const k = puff.age / puff.life
        const p = puff.position
        const v = puff.velocity
        // A little swirl, different for each puff.
        puff.swirl += dt * 2.3
        v.x += Math.cos(puff.swirl) * dt * 0.35
        v.z += Math.sin(puff.swirl * 1.3) * dt * 0.35
        p.addScaledVector(v, dt)
        const size = puff.size + puff.grow * (1 - (1 - k) * (1 - k))
        // A puff is a flat disc facing the camera: its middle stays high enough that it rests ON the floor
        // (anything below the floor is not drawn, which would cut its lower half off with a straight edge).
        const floorLevel = size * 0.42
        if (p.y <= floorLevel && v.y < 0) {
          // Exhaust that reaches the floor rolls outward along it.
          const flat = Math.hypot(v.x, v.z)
          const push = Math.max(0, -v.y) * 0.85
          if (flat > 1e-3) {
            v.x += (v.x / flat) * push
            v.z += (v.z / flat) * push
          } else {
            v.x += Math.cos(puff.swirl) * push
            v.z += Math.sin(puff.swirl) * push
          }
          v.y = 0.02
        }
        p.y = Math.max(p.y, floorLevel)
        v.multiplyScalar(1 - Math.min(0.95, dt * (puff.kind === 'dust' ? 1.9 : 1.4))) // air slows it
        v.y += dt * (puff.kind === 'dust' ? 0.12 : 0.35) // warm exhaust rises; dust only lifts a little
        if (puff.kind === 'exhaust') colour.lerpColors(WARM, EXHAUST, Math.min(1, puff.age * 9)) // warm only near the flame
        else colour.copy(DUST)
        offsets.setXYZ(index, p.x, p.y, p.z)
        sizes.setX(index, size)
        alphas.setX(index, puff.opacity * Math.min(1, puff.age * 10) * (1 - k) * (1 - k * 0.3))
        tints.setXYZ(index, colour.r, colour.g, colour.b)
      })
      for (const attribute of [offsets, sizes, alphas, tints]) attribute.needsUpdate = true
      return any
    },
    dispose() {
      scene.remove(mesh)
      quad.dispose()
      geometry.dispose()
      material.dispose()
    },
  }
}
