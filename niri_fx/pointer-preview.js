// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Julien Turbide
// Browser adaptation of the spring and shader in experimental/niri-pointer-wobble.patch.
// Source: https://github.com/jturbide/niri-fx/blob/main/experimental/niri-pointer-wobble.patch
// License: https://github.com/jturbide/niri-fx/blob/main/experimental/COPYING-NIRI
// The native analytical solution uses seconds and logical pixels. This public
// browser API accepts milliseconds, matching performance.now() and combo seeks.
/* exported createPointerSpring, createPointerDemo, POINTER_PREVIEW_SHADER */

function createPointerSpring(config, anchor = [0.5, 0.06], nowMs = 0) {
  if (
    !config ||
    !Number.isFinite(config.strength) ||
    config.strength < 0 ||
    config.strength > 2 ||
    !Number.isInteger(config.damping) ||
    config.damping < 10 ||
    config.damping > 100 ||
    !Number.isInteger(config.frequency) ||
    config.frequency < 2 ||
    config.frequency > 16
  )
    throw new Error("Pointer preview requires valid strength, damping and frequency settings.");
  function timestamp(value) {
    if (!Number.isFinite(value) || value < 0)
      throw new Error("Pointer preview time must be finite and nonnegative.");
    return value;
  }
  function point(value) {
    if (!Array.isArray(value) || value.length !== 2 || !value.every(Number.isFinite))
      throw new Error("Pointer anchor must contain two finite coordinates.");
    return [...value];
  }
  const omega = 2 * Math.PI * config.frequency,
    damping = config.damping / 100,
    strength = config.strength;
  let position = [0, 0],
    velocity = [0, 0],
    sampledAt = timestamp(nowMs),
    releasedAt = null,
    anchorFrom = point(anchor),
    anchorTo = [...anchorFrom],
    anchorAt = nowMs;

  function moving() {
    return (
      Math.abs(position[0]) + Math.abs(position[1]) > 0.01 ||
      Math.abs(velocity[0]) + Math.abs(velocity[1]) > 0.1
    );
  }
  function atAnchor(now) {
    const t = Math.min(Math.max(0, now - anchorAt) / 80, 1);
    if (t >= 1) return [...anchorTo];
    const mix = t * t * (3 - 2 * t);
    return anchorFrom.map((from, i) => from + (anchorTo[i] - from) * mix);
  }
  function envelope() {
    if (releasedAt === null) return [1, 0];
    const elapsed = Math.max(0, sampledAt - releasedAt) / 1000,
      t = Math.min(1, Math.max(0, (elapsed - 1.5) / 0.5)),
      smooth = t ** 3 * (10 - 15 * t + 6 * t ** 2),
      derivative = (-30 * t ** 2 * (1 - t) ** 2) / 0.5;
    return [1 - smooth, derivative];
  }
  function advance(now) {
    timestamp(now);
    const dt = Math.max(0, now - sampledAt) / 1000;
    sampledAt = Math.max(sampledAt, now);
    if (releasedAt !== null && now - releasedAt >= 2000) {
      position = [0, 0];
      velocity = [0, 0];
      return;
    }
    const decay = Math.exp(-damping * omega * dt);
    for (let i = 0; i < 2; i++) {
      const x = position[i],
        v = velocity[i];
      if (damping >= 1) {
        const b = v + omega * x;
        position[i] = (x + b * dt) * decay;
        velocity[i] = (v - omega * b * dt) * decay;
      } else {
        const rate = damping * omega,
          wd = omega * Math.sqrt(1 - damping * damping),
          sin = Math.sin(wd * dt),
          cos = Math.cos(wd * dt),
          b = (v + rate * x) / wd;
        position[i] = decay * (x * cos + b * sin);
        velocity[i] = decay * (v * cos - (rate * b + wd * x) * sin);
      }
    }
    if (!moving()) {
      position = [0, 0];
      velocity = [0, 0];
    }
  }
  function grab(nextAnchor, now) {
    const next = point(nextAnchor);
    advance(now);
    const [scale, derivative] = envelope();
    velocity = velocity.map((value, i) => value * scale + position[i] * derivative);
    position = position.map((value) => value * scale);
    anchorFrom = atAnchor(now);
    anchorTo = next;
    anchorAt = now;
    releasedAt = null;
  }
  function push(delta, now) {
    timestamp(now);
    // Match native defensive handling: invalid input does not advance time or
    // alter the existing spring, and huge finite events are bounded first.
    if (!Array.isArray(delta) || delta.length !== 2 || !delta.every(Number.isFinite)) return;
    advance(now);
    if (releasedAt !== null) grab(atAnchor(now), now);
    velocity = velocity.map(
      (value, i) => value - Math.min(1e6, Math.max(-1e6, delta[i])) * omega * strength,
    );
    const radius = Math.min(Math.hypot(...position), 64),
      maxVelocity = omega * Math.sqrt(64 ** 2 - radius ** 2),
      speed = Math.hypot(...velocity);
    if (speed > maxVelocity) velocity = velocity.map((value) => (value * maxVelocity) / speed);
  }
  function release(now) {
    advance(now);
    releasedAt = now;
  }
  function sample(now) {
    advance(now);
    const scale = envelope()[0];
    return {
      deformation: position.map((value) => value * scale),
      anchor: atAnchor(now),
      released: releasedAt !== null,
      moving: moving(),
    };
  }
  return Object.freeze({ push, grab, release, sample });
}

function createPointerDemo(config) {
  // Snapshot the controls before building a deterministic 120 Hz input trace.
  // Render cadence never creates input events, so GIF captures and backwards
  // combo seeks produce the same state as ordinary animation playback.
  const settings = Object.freeze({ ...config });
  createPointerSpring(settings);
  const dragMs = 1200,
    durationMs = dragMs + 2000,
    waypoints = [
      [0, 0],
      [116, 32],
      [-96, -24],
      [0, 0],
    ],
    events = [];
  let previous = [0, 0];
  for (let step = 1; step <= 144; step++) {
    const now = (step * dragMs) / 144,
      segment = Math.min(2, Math.floor(now / 400)),
      fraction = (now - segment * 400) / 400,
      offset = waypoints[segment].map(
        (from, i) => from + (waypoints[segment + 1][i] - from) * fraction,
      );
    events.push(
      Object.freeze({
        now,
        offset: Object.freeze(offset),
        delta: Object.freeze(offset.map((value, i) => value - previous[i])),
      }),
    );
    previous = offset;
  }
  Object.freeze(events);
  function sample(elapsedMs) {
    if (!Number.isFinite(elapsedMs)) throw new Error("Pointer preview time must be finite.");
    const elapsed = Math.min(durationMs, Math.max(0, elapsedMs)),
      spring = createPointerSpring(settings);
    let offset = [0, 0];
    for (const event of events) {
      if (event.now > elapsed) break;
      spring.push(event.delta, event.now);
      offset = [...event.offset];
    }
    if (elapsed >= dragMs) spring.release(dragMs);
    return {
      ...spring.sample(elapsed),
      offset,
      phase: elapsed < dragMs ? "drag" : "settle",
      elapsedMs: elapsed,
      durationMs,
    };
  }
  return Object.freeze({ durationMs, dragMs, sample });
}

// Native shader adapter: the Studio texture exactly covers its synthetic window,
// so geometry-to-texture is identity and tile alpha is one. The caller provides
// normalized destination coordinates and logical-pixel size. The deformation,
// inverse map, texture bounds and premultiplied color remain native-identical.
const POINTER_PREVIEW_SHADER = `
uniform sampler2D niri_tex;
uniform vec2 niri_pointer_anchor;
uniform vec2 niri_pointer_deformation;
vec2 displacement(vec2 uv, vec2 shift) {
    vec2 relative = uv - niri_pointer_anchor;
    float weight = min(dot(relative, relative), 1.0);
    return shift * weight;
}
vec4 pointer_color(vec2 coords, vec2 size) {
    vec2 dest = coords;
    float limit = min(64.0, min(size.x, size.y) * 0.12);
    float magnitude = length(niri_pointer_deformation);
    vec2 shift = niri_pointer_deformation * min(1.0, limit / max(magnitude, 0.0001));
    shift /= max(size, vec2(1.0));
    vec2 source = dest;
    for (int i = 0; i < 5; i++) {
        source = dest - displacement(source, shift);
    }
    vec2 uv = source;
    vec4 color = texture2D(niri_tex, uv);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) color = vec4(0.0);
    return color;
}
`;
