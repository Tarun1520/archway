/**
 * Shaders for the grass.
 *
 * Every blade of grass is the same small strip of triangles. The vertex
 * shader runs for each corner of each blade and decides where that corner
 * ends up: it narrows the strip to a point, turns it to face a random
 * direction, bends it, and moves it to the blade's place on the hill.
 *
 * Per-blade values (different for every blade, set once in createGrass.ts):
 *   aOffset  where the blade's root is
 *   aBlade   x: height, y: facing angle, z: random 0-1, w: how light the tip is
 *
 * Values for the whole meadow:
 *   uTime    seconds since start; makes the wind move
 */
export const grassVertexShader = /* glsl */ `
  attribute vec3 aOffset;
  attribute vec4 aBlade;

  uniform float uTime;

  varying float vAlong; // 0 at the root, 1 at the tip
  varying float vTint;
  varying float vFar; // 0 close to the viewer, 1 far up the hill
  varying float vShade; // 1 in sunlight, lower in the furniture's shadow

  const float BLADE_WIDTH = 0.022;

  // Distance from point p to a rectangle centered on the origin with half-size b.
  float distanceToBox(vec2 p, vec2 b) {
    return length(max(abs(p) - b, 0.0));
  }

  void main() {
    float along = uv.y;
    float height = aBlade.x;

    // Narrow the strip toward the tip, and turn it to its facing angle.
    float width = BLADE_WIDTH * (1.0 - along * 0.88);
    float facingX = cos(aBlade.y);
    float facingZ = sin(aBlade.y);
    vec3 point = vec3(position.x * width * facingX, along * height, position.x * width * facingZ);

    // Wind: two slow waves that travel across the hill. Each blade joins in
    // slightly out of step with its neighbours.
    float gust = sin(uTime * 1.5 + aOffset.x * 1.1 + aBlade.z * 6.0) * 0.6
      + sin(uTime * 0.6 + aOffset.z * 1.6 + aBlade.z * 11.0) * 0.4;

    // Bending grows with the square of the height, so the root stays put and
    // the tip moves the most. Each blade also has its own permanent lean.
    float bend = along * along * height;
    float lean = aBlade.z * 6.2832;
    point.x += bend * (0.20 + 0.24 * sin(lean) + 0.20 * gust);
    point.z += bend * 0.24 * cos(lean);
    point.y -= bend * 0.10; // a bent blade reaches a little less high

    vec3 world = point + aOffset;

    vAlong = along;
    vTint = aBlade.w;
    vFar = clamp((3.5 - aOffset.z) / 9.5, 0.0, 1.0);

    // Shadows on the grass. The sun is behind and to the left, so the desk
    // and the chair throw their shadows forward and to the right. Each
    // shadow is a soft-edged shape placed where the real one would fall.
    float deskShadow = 1.0 - smoothstep(0.0, 0.40, distanceToBox(aOffset.xz - vec2(0.34, 0.26), vec2(0.70, 0.40)));
    float chairShadow = 1.0 - smoothstep(0.10, 0.62, length(aOffset.xz - vec2(-0.64, 1.02)));
    vShade = 1.0 - 0.50 * max(deskShadow, chairShadow);

    gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
  }
`

export const grassFragmentShader = /* glsl */ `
  precision highp float;

  varying float vAlong;
  varying float vTint;
  varying float vFar;
  varying float vShade;

  const vec3 ROOT = vec3(0.070, 0.165, 0.060);
  const vec3 BLADE = vec3(0.270, 0.470, 0.170);
  const vec3 TIP = vec3(0.720, 0.780, 0.380);
  const vec3 HAZE = vec3(0.900, 0.860, 0.820);

  void main() {
    // Dark at the root, green in the middle, pale and sunlit at the tip.
    vec3 color = mix(ROOT, BLADE, smoothstep(0.0, 0.55, vAlong));
    color = mix(color, TIP, smoothstep(0.45, 1.0, vAlong) * (0.30 + 0.70 * vTint));

    // Grass nearest the viewer is a little darker; it frames the picture.
    color *= mix(0.62, 1.0, smoothstep(0.0, 0.35, vFar)) * vShade;

    // The farthest grass takes on a little of the valley's haze.
    color = mix(color, HAZE, smoothstep(0.55, 1.0, vFar) * 0.22);

    gl_FragColor = vec4(color, 1.0);
  }
`
