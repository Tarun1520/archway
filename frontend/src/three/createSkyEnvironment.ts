import { BackSide, Mesh, PMREMGenerator, Scene, ShaderMaterial, SphereGeometry } from 'three'
import type { Texture, WebGLRenderer } from 'three'

/**
 * Builds the "environment": the surroundings that shiny surfaces reflect.
 *
 * Chrome and aluminium have almost no color of their own. What you see in
 * them is a reflection of what is around them. Without an environment they
 * would render nearly black.
 *
 * The environment here is a simple dome painted with the scene's sky colors:
 * blue overhead, pale at the horizon, a warm bright patch where the sun is
 * rising, and grass green underfoot. three.js photographs that dome once and
 * turns it into a reflection map (the PMREMGenerator does this).
 */
export interface SkyEnvironment {
  texture: Texture
  dispose(): void
}

const vertexShader = /* glsl */ `
  varying vec3 vDirection;

  void main() {
    vDirection = normalize(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = /* glsl */ `
  precision highp float;
  varying vec3 vDirection;

  void main() {
    vec3 direction = normalize(vDirection);
    float up = direction.y;

    vec3 zenith = vec3(0.36, 0.55, 1.00);
    vec3 horizon = vec3(1.00, 0.86, 0.78);
    vec3 ground = vec3(0.16, 0.26, 0.11);

    vec3 color = mix(horizon, zenith, smoothstep(0.0, 0.75, up));
    color = mix(color, ground, smoothstep(0.02, -0.25, up));

    // The rising sun: behind and to the left, low in the sky. Values above
    // 1.0 are "brighter than white", which gives metal a crisp highlight.
    vec3 sunDirection = normalize(vec3(-0.62, 0.34, -0.70));
    float towardSun = max(dot(direction, sunDirection), 0.0);
    color += vec3(1.0, 0.78, 0.58) * (pow(towardSun, 6.0) * 1.4 + pow(towardSun, 60.0) * 6.0);

    gl_FragColor = vec4(color, 1.0);
  }
`

export function createSkyEnvironment(renderer: WebGLRenderer): SkyEnvironment {
  const geometry = new SphereGeometry(10, 48, 24)
  const material = new ShaderMaterial({ vertexShader, fragmentShader, side: BackSide }) // seen from inside
  const dome = new Mesh(geometry, material)

  const domeScene = new Scene()
  domeScene.add(dome)

  const generator = new PMREMGenerator(renderer)
  const renderTarget = generator.fromScene(domeScene, 0.03) // the number adds a slight blur

  // The dome was only needed for the photograph.
  geometry.dispose()
  material.dispose()
  generator.dispose()

  return {
    texture: renderTarget.texture,
    dispose() {
      renderTarget.dispose()
    },
  }
}
