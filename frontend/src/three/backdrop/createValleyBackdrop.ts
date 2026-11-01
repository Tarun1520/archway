import { Mesh, PlaneGeometry, ShaderMaterial, Vector2 } from 'three'
import type { ScenePart } from '../scenePart'
import { BACKDROP_ZOOM } from '../sceneSettings'
import { valleyFragmentShader, valleyVertexShader } from './valleyShaders.glsl'

/**
 * The backdrop: one rectangle covering the whole screen, painted by the
 * valley shader. It is drawn first and everything else is drawn on top.
 *
 * A "uniform" is a value sent from JavaScript into a shader. This part keeps
 * them up to date: the canvas size, the time, the pointer, and how far the
 * scroll zoom has gone.
 */
export function createValleyBackdrop(): ScenePart {
  const uniforms = {
    uResolution: { value: new Vector2(1, 1) },
    uTime: { value: 0 },
    uPointer: { value: new Vector2(0, 0) },
    uScale: { value: 1 },
    uRise: { value: 0 },
    uBlur: { value: 0 },
  }

  const geometry = new PlaneGeometry(2, 2)
  const material = new ShaderMaterial({
    uniforms,
    vertexShader: valleyVertexShader,
    fragmentShader: valleyFragmentShader,
    // It is a flat picture, so it takes no part in the 3D depth sorting.
    depthTest: false,
    depthWrite: false,
  })

  const mesh = new Mesh(geometry, material)
  mesh.renderOrder = -1 // draw before everything else
  mesh.frustumCulled = false // never skip it for being "outside the camera's view"

  return {
    object: mesh,
    update(timeSeconds) {
      uniforms.uTime.value = timeSeconds
    },
    setResolution(width, height) {
      uniforms.uResolution.value.set(width, height)
    },
    setPointer(x, y) {
      uniforms.uPointer.value.set(x, y)
    },
    setZoom(progress) {
      // As the camera closes in on the laptop and tilts down, the far-away
      // valley grows a little, slides up the screen, and drifts out of focus.
      uniforms.uScale.value = 1 + (BACKDROP_ZOOM.endScale - 1) * progress
      uniforms.uRise.value = BACKDROP_ZOOM.endRise * progress
      uniforms.uBlur.value = BACKDROP_ZOOM.endBlur * Math.min(progress * 1.4, 1)
    },
    dispose() {
      geometry.dispose()
      material.dispose()
    },
  }
}
