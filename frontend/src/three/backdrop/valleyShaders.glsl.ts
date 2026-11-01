/**
 * The painted backdrop: a misty mountain valley at dawn.
 *
 * Nothing here is a photograph or a 3D model. It is a "fragment shader": a
 * small program the graphics card runs once for every pixel to decide that
 * pixel's color. This one paints, from back to front:
 *
 *   1. a dawn sky with a warm glow on the left
 *   2. two distant mountain ridges
 *   3. the valley floor, with a river winding toward the horizon
 *   4. five forested slopes that reach in from alternating sides
 *
 * The mountain shapes come from "noise": smooth random numbers that look like
 * natural terrain.
 *
 * Inputs set from JavaScript (see createValleyBackdrop.ts):
 *   uResolution  canvas size in device pixels
 *   uTime        seconds since start (drives cloud drift and river shimmer)
 *   uPointer     eased pointer position, -1 to 1 (small parallax)
 *   uScale       1 = normal size; larger = the picture is magnified about the
 *                horizon, as it would be when a camera moves toward it
 *   uRise        how far the picture has slid up the screen (0.18 = 18% of its height)
 *   uBlur        0 = sharp, 1 = out of focus (fine detail fades, edges soften)
 */

/**
 * Vertex shader: stretches one rectangle over the whole screen and hands each
 * pixel its position (`vUv`, from 0 to 1) to the fragment shader. It ignores
 * the camera on purpose, so the backdrop never moves with the 3D scene.
 */
export const valleyVertexShader = /* glsl */ `
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 1.0, 1.0);
  }
`

export const valleyFragmentShader = /* glsl */ `
  precision highp float;

  uniform vec2 uResolution;
  uniform float uTime;
  uniform vec2 uPointer;
  uniform float uScale;
  uniform float uRise;
  uniform float uBlur;

  varying vec2 vUv;

  // Where the valley meets the sky (0 = bottom of the canvas, 1 = top).
  const float HORIZON = 0.50;

  // --- Palette -------------------------------------------------------------
  // A bright, clear morning: blue overhead, peach where the sun is rising,
  // sunlit green slopes, white mist.
  const vec3 SKY_TOP = vec3(0.300, 0.440, 0.720);
  const vec3 SKY_MID = vec3(0.560, 0.680, 0.900);
  const vec3 SKY_LOW = vec3(1.000, 0.870, 0.800);
  const vec3 SUN_GLOW = vec3(1.000, 0.700, 0.560);
  const vec3 HAZE = vec3(0.930, 0.880, 0.870);
  const vec3 CLOUD = vec3(1.000, 0.975, 0.955);
  const vec3 RIDGE_FAR = vec3(0.600, 0.660, 0.800);
  const vec3 RIDGE_MID = vec3(0.280, 0.460, 0.380);
  const vec3 RIDGE_NEAR = vec3(0.085, 0.215, 0.115);
  const vec3 MEADOW = vec3(0.430, 0.600, 0.330);
  const vec3 RIVER = vec3(0.960, 0.930, 0.930);

  // --- Noise helpers -------------------------------------------------------
  // hash: turns a number into a repeatable pseudo-random value from 0 to 1.
  float hash11(float n) {
    return fract(sin(n * 127.1) * 43758.5453123);
  }

  float hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
  }

  // noise: random values at whole numbers, smoothly blended in between.
  float noise1(float x) {
    float i = floor(x);
    float f = fract(x);
    float u = f * f * (3.0 - 2.0 * f);
    return mix(hash11(i), hash11(i + 1.0), u);
  }

  float noise2(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
  }

  // fbm ("fractal Brownian motion"): several layers of noise added together,
  // each finer and fainter than the last. It is what makes a line look like
  // terrain, or a blob look like a cloud, instead of a smooth wave.
  float fbm1(float x) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 5; i++) {
      value += amplitude * noise1(x);
      x = x * 2.07 + 13.7;
      amplitude *= 0.5;
    }
    return value;
  }

  float fbm2(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
      value += amplitude * noise2(p);
      p = p * 2.03 + 7.3;
      amplitude *= 0.5;
    }
    return value;
  }

  // A row of pointed tree tops. Squaring the random size leaves gaps: many
  // small trees and a few tall ones, like a real tree line.
  float treeTips(float along, float seed) {
    float tip = 1.0 - abs(fract(along) * 2.0 - 1.0);
    float size = hash11(floor(along) + seed * 100.0);
    return tip * size * size;
  }

  /**
   * Paints one mountain ridge on top of the picture so far.
   *
   *   crest  height of the ridge line at this pixel's x
   *   foot   height where the ridge meets the valley floor (-1.0 = fills to the bottom)
   *   depth  0 = far away (pale, smooth), 1 = close (dark, with visible trees)
   *   lit    0 = this slope faces away from the dawn light, 1 = it faces toward it
   *   layer  a different number per ridge, so each gets its own random shapes
   */
  vec3 paintRidge(vec3 color, vec2 uv, float x, float pixel, float crest, float foot, float depth, float lit, float layer) {
    // Trees: pointed tips along the crest, only on closer ridges. Two rows of
    // different sizes overlap so the edge never looks regular.
    float forest = smoothstep(0.15, 0.45, depth);
    float density = mix(260.0, 55.0, depth);
    float treeLine = treeTips(x * density + layer * 17.0, layer)
      + 0.55 * treeTips(x * density * 2.3 + layer * 5.0, layer + 9.0);
    crest += treeLine * mix(0.003, 0.016, depth) * forest * (1.0 - uBlur);

    // 1 inside the ridge, 0 outside, with soft edges.
    // Out of focus, a hard edge becomes a wide soft one.
    float edge = pixel * 1.5 + uBlur * 0.045;
    float mask = smoothstep(crest + edge, crest - edge, uv.y);

    // The foot is an uneven, soft line, so the slope melts into the mist
    // on the valley floor instead of ending in a straight cut.
    float unevenFoot = foot + (fbm1(x * 3.0 + layer * 23.0) - 0.5) * 0.06;
    mask *= smoothstep(unevenFoot - 0.03, unevenFoot + 0.10, uv.y);

    // Far ridges are pale and blue (there is more air between us and them).
    vec3 ridge = depth < 0.5
      ? mix(RIDGE_FAR, RIDGE_MID, depth * 2.0)
      : mix(RIDGE_MID, RIDGE_NEAR, depth * 2.0 - 1.0);

    // Mottled patches (large) and speckles (tree-sized) suggest a forest canopy.
    float canopy = fbm2(vec2(x * density * 0.22 + layer * 3.0, uv.y * density * 0.30));
    float speckle = noise2(vec2(x * density * 1.3 + layer, uv.y * density * 1.7));
    ridge *= mix(1.0, 0.66 + 0.68 * mix(canopy, speckle, 0.45 * (1.0 - uBlur)), forest * (1.0 - 0.6 * uBlur));

    float below = max(crest - uv.y, 0.0);

    // The dawn light comes from the left. It warms distant slopes, brushes
    // the tree tops, and lights the slopes that face it.
    ridge += vec3(0.130, 0.060, 0.030) * (1.0 - depth) * smoothstep(0.75, 0.10, uv.x);
    ridge += vec3(0.200, 0.180, 0.070) * forest * lit * (0.35 + 0.65 * canopy) * exp(-below * 4.0);
    ridge *= 1.0 + 0.55 * forest * exp(-below * 45.0);

    // Haze thickens toward the bottom of each ridge and around its foot.
    ridge = mix(ridge, HAZE, smoothstep(0.0, 0.20, below) * mix(0.55, 0.06, depth));
    ridge = mix(ridge, HAZE, (1.0 - smoothstep(unevenFoot, unevenFoot + 0.16, uv.y)) * mix(0.65, 0.30, depth));

    // Low clouds: soft patches lying just below the crest, drifting sideways.
    vec2 cloudPoint = vec2(x * 1.5 + uTime * 0.008 * (1.0 + layer) + layer * 7.0, uv.y * 8.0 - layer * 3.0);
    float cloud = smoothstep(0.50, 0.72, fbm2(cloudPoint));
    cloud *= smoothstep(0.0, 0.04, below) * smoothstep(0.24, 0.07, below);
    ridge = mix(ridge, CLOUD, cloud * mix(0.80, 0.25, depth));

    return mix(color, ridge, mask);
  }

  void main() {
    float aspect = uResolution.x / uResolution.y;

    // Magnify the picture about the middle of the horizon. Dividing the
    // distance from that point by uScale makes everything look uScale times
    // larger, the way the view grows when a camera moves forward.
    vec2 anchor = vec2(0.5, HORIZON);
    vec2 uv = (vUv - vec2(0.0, uRise) - anchor) / uScale + anchor;

    // x measured from the center, in units of canvas height, so shapes keep
    // their proportions on wide and narrow screens alike.
    float x = (uv.x - 0.5) * aspect;
    float pixel = 1.0 / (uResolution.y * uScale);

    // --- 1. Sky ------------------------------------------------------------
    float skyHeight = smoothstep(HORIZON, 1.0, uv.y);
    vec3 color = mix(SKY_LOW, SKY_MID, smoothstep(0.0, 0.42, skyHeight));
    color = mix(color, SKY_TOP, smoothstep(0.30, 1.0, skyHeight));

    // A warm glow in the upper left, where the sun is about to rise.
    vec2 toGlow = vec2((uv.x - 0.30) * 1.5, (uv.y - 0.74) * 1.9);
    float glow = exp(-dot(toGlow, toGlow) * 5.0);
    color = mix(color, SUN_GLOW, glow * 0.80);

    // Thin, high streaks of cloud that catch the glow.
    float wisps = fbm2(vec2(x * 1.3 + uTime * 0.004, uv.y * 7.0));
    color += vec3(0.22, 0.14, 0.12) * smoothstep(0.50, 0.80, wisps) * smoothstep(0.55, 0.80, uv.y) * (0.4 + glow);

    // A band of pale haze sitting on the horizon.
    color = mix(color, HAZE, exp(-abs(uv.y - HORIZON) * 9.0) * 0.55);

    // --- 2. Two distant ridges, edge to edge -------------------------------
    float farCrest = 0.545 + (fbm1(x * 2.6 + 3.1) - 0.5) * 0.060;
    color = paintRidge(color, uv, x, pixel, farCrest, -1.0, 0.0, 0.0, 0.0);

    float secondCrest = 0.505 + (fbm1(x * 2.1 + 41.7 + uPointer.x * 0.004) - 0.5) * 0.070;
    color = paintRidge(color, uv, x, pixel, secondCrest, -1.0, 0.18, 0.0, 1.0);

    // --- 3. Valley floor and river -----------------------------------------
    float floorTop = 0.468 + (fbm1(x * 3.0 + 5.0) - 0.5) * 0.020;
    float floorEdge = pixel * 1.5 + uBlur * 0.045;
    float floorMask = smoothstep(floorTop + floorEdge, floorTop - floorEdge, uv.y);

    // Meadow: paler in the distance, with a little patchiness.
    vec3 meadow = mix(MEADOW, HAZE, smoothstep(0.26, floorTop, uv.y) * 0.60);
    meadow *= 0.85 + 0.30 * (1.0 - 0.7 * uBlur) * fbm2(vec2(x * 9.0, uv.y * 40.0));

    // "riverDistance" grows quickly toward the horizon. Dividing by it makes the
    // river narrower and its bends smaller the farther away it is, which is
    // how perspective makes a winding river look.
    float toward = clamp((uv.y - 0.08) / (floorTop - 0.08), 0.0, 1.0);
    float riverDistance = 1.0 / (1.06 - toward);
    float riverCenter = sin(riverDistance * 1.7 + 0.4) * 0.11 / riverDistance - uPointer.x * 0.004;
    float riverHalfWidth = 0.034 / riverDistance;
    float river = smoothstep(riverHalfWidth + uBlur * 0.012, riverHalfWidth * 0.55 - uBlur * 0.004, abs(x - riverCenter));
    float shimmer = 0.92 + 0.08 * (1.0 - uBlur) * sin(uv.y * 900.0 / riverDistance + uTime * 1.5);
    meadow = mix(meadow, RIVER * shimmer, river * 0.78);

    color = mix(color, meadow, floorMask);

    // --- 4. Forested slopes reaching in from alternating sides -------------
    // Each slope is tall at its own edge of the screen and tapers to the
    // valley floor near the middle, leaving the river in view between them.
    for (int k = 0; k < 5; k++) {
      float n = float(k);
      float near = n / 4.0; // 0 = farthest slope, 1 = nearest

      // Even slopes come from the right, odd ones from the left.
      float direction = mod(n, 2.0) < 0.5 ? 1.0 : -1.0;

      // 0 at the opposite edge of the screen, 1 at this slope's own edge.
      float across = 0.5 + direction * (uv.x - 0.5);

      // Where the slope begins to rise, and how far it has risen here.
      float tipAt = mix(0.34, 0.50, near);
      float rise = pow(smoothstep(tipAt, 1.10, across), 0.85);

      float low = mix(0.445, 0.04, near);
      float high = mix(0.56, 0.69, near);
      float sampleX = x * mix(2.2, 0.9, near) + n * 53.1 + uPointer.x * near * 0.04;

      // Two sizes of unevenness: broad shoulders and dips, then finer bumps.
      float shoulders = (fbm1(sampleX * 0.45 + 9.0) - 0.5) * mix(0.11, 0.27, near);
      float bumps = (fbm1(sampleX) - 0.5) * mix(0.05, 0.10, near);
      float crest = low + (high - low) * rise + (shoulders + bumps) * (0.45 + 0.55 * rise);

      // The foot of the slope drops away toward the viewer.
      float foot = low - max(across - tipAt, 0.0) * mix(0.10, 0.90, near);

      // Slopes on the right face the dawn light; slopes on the left face away.
      float lit = direction > 0.0 ? 1.0 : 0.15;

      color = paintRidge(color, uv, x, pixel, crest, foot, mix(0.32, 1.0, near), lit, n + 2.0);
    }

    // --- Finishing ---------------------------------------------------------
    // Darken the left and right edges to hold the eye in the middle.
    color *= 1.0 - 0.24 * smoothstep(0.26, 0.50, abs(vUv.x - 0.5));

    // Fine grain hides the faint stripes ("banding") that smooth gradients
    // can show on screens.
    float grain = hash21(gl_FragCoord.xy + fract(uTime) * 100.0) - 0.5;
    color += grain * 0.016;

    gl_FragColor = vec4(color, 1.0);
  }
`
