// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (c) 2026 Julien Turbide
// Adapted from experimental/niri-fragment-drag.patch.
// Source: https://github.com/jturbide/niri-fx/blob/main/experimental/niri-fragment-drag.patch
// License: https://github.com/jturbide/niri-fx/blob/main/experimental/COPYING-NIRI
// Fixed synthetic geometry, square cells and pointer input only. This adapter
// does not simulate Niri layout, damage, capture policy or output migration.
/* exported createFragmentMotion, createFragmentDemo, createFragmentRenderer, fragmentPreviewMesh, FRAGMENT_PREVIEW_MATERIAL */

const fragmentClamp = (value, low, high) => Math.min(high, Math.max(low, value));
const fragmentNorm = (value) => Math.hypot(...value);
const fragmentAdd = (a, b) => [a[0] + b[0], a[1] + b[1]];
const fragmentSub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const fragmentScale = (value, scale) => value.map((part) => part * scale);
const fragmentLimited = (value, bound) =>
  fragmentScale(value, Math.min(bound / Math.max(fragmentNorm(value), bound), 1));
const fragmentEqual = (a, b) => a[0] === b[0] && a[1] === b[1];

function fragmentTime(value) {
  if (!Number.isFinite(value) || value < 0 || value > Number.MAX_SAFE_INTEGER / 1e6)
    throw new Error("Fragment preview time must be finite, nonnegative and representable.");
  // Rust Duration resolves nanoseconds; retaining that boundary avoids moving a
  // delayed target across an integration slice due to fractional timestamps.
  return Math.round(value * 1e6) / 1e6;
}
function fragmentPoint(value) {
  if (!Array.isArray(value) || value.length !== 2 || !value.every(Number.isFinite))
    throw new Error("Fragment preview requires two finite coordinates.");
  return [...value];
}
function fragmentHash(id, salt) {
  let value = (BigInt(id[0] >>> 0) << 32n) ^ BigInt(id[1] >>> 0) ^ BigInt(salt);
  value ^= value >> 30n;
  value = BigInt.asUintN(64, value * 0xbf58476d1ce4e5b9n);
  value ^= value >> 27n;
  value = BigInt.asUintN(64, value * 0x94d049bb133111ebn);
  value ^= value >> 31n;
  return Number(value >> 11n) / 2 ** 53;
}
function fragmentSpring() {
  return {
    value: [0, 0],
    velocity: [0, 0],
    finish(target) {
      this.value = [...target];
      this.velocity = [0, 0];
    },
    advance(target, seconds, response) {
      const omega = 3.889720169867429 / (response / 1000),
        lag = fragmentSub(this.value, target),
        b = fragmentAdd(this.velocity, fragmentScale(lag, omega)),
        decay = Math.exp(-omega * seconds);
      this.value = fragmentAdd(
        target,
        fragmentScale(fragmentAdd(lag, fragmentScale(b, seconds)), decay),
      );
      this.velocity = fragmentScale(
        fragmentSub(this.velocity, fragmentScale(b, omega * seconds)),
        decay,
      );
      if (
        fragmentNorm(fragmentSub(this.value, target)) < 0.0001 &&
        fragmentNorm(this.velocity) < 0.001
      )
        this.finish(target);
    },
  };
}

function createFragmentMotion(settings, options = {}) {
  // Canonical document validation happens before entering the preview. Defensive
  // bounds here keep this standalone API safe when called outside Studio.
  const ranges = {
    batches: [1, 4096, true],
    delay_near_ms: [0, 600, true],
    delay_far_ms: [0, 600, true],
    delay_jitter: [0, 1],
    response_near_ms: [20, 800, true],
    response_far_ms: [20, 800, true],
    response_jitter: [0, 1],
    distance_exponent: [0, 4],
    max_lag: [1, 1024, true],
    pin_radius: [0, 256],
    press_spread: [0, 128],
    press_response_ms: [20, 800, true],
    rotation_degrees: [0, 60],
    rotation_response_ms: [20, 800, true],
    rotation_speed: [1, 5000, true],
    tilt: [0, 1.1],
    release_ms: [200, 2000, true],
  };
  if (
    !settings ||
    Object.keys(settings).length !== Object.keys(ranges).length + 1 ||
    !["movement", "random", "none"].includes(settings.rotation_mode) ||
    Object.entries(ranges).some(
      ([key, [low, high, integer]]) =>
        !Number.isFinite(settings[key]) ||
        settings[key] < low ||
        settings[key] > high ||
        (integer && !Number.isInteger(settings[key])),
    ) ||
    settings.distance_exponent <= 0 ||
    settings.delay_near_ms > settings.delay_far_ms ||
    settings.response_near_ms > settings.response_far_ms
  )
    throw new Error("Fragment preview requires a complete valid response.");
  const config = Object.freeze({ ...settings }),
    size = fragmentPoint(options.size || [600, 380]),
    particles = options.particles ?? 800,
    tileSetting = options.tile ?? 28;
  if (
    size.some((value) => value <= 0 || value > 1e6) ||
    !Number.isInteger(particles) ||
    particles < 0 ||
    particles > 4096 ||
    !Number.isFinite(tileSetting) ||
    tileSetting < 8 ||
    tileSetting > 128
  )
    throw new Error("Fragment preview requires valid size, particles and tile settings.");
  const tile = particles ? Math.max(4, Math.sqrt((size[0] * size[1]) / particles)) : tileSetting,
    origin = size.map((value) => (value - Math.ceil(value / tile) * tile) * 0.5),
    first = origin.map((value) => Math.floor(-value / tile)),
    last = origin.map((value, axis) => Math.ceil((size[axis] - value) / tile));
  if ((last[0] - first[0]) * (last[1] - first[1]) > 4096)
    throw new Error("Fragment preview grid exceeds the native 4096 cell limit.");
  let sampledAt = fragmentTime(options.nowMs ?? 0),
    anchor = fragmentPoint(options.anchor || [0.5, 0.5]),
    held = false,
    releasedAt = null,
    target = [0, 0],
    history = [{ at: sampledAt, position: [...target] }];
  const cells = [];
  function configure(cell, fresh) {
    const point = anchor.map((value, axis) => value * size[axis]),
      offset = fragmentSub(cell.center, point),
      distance = fragmentNorm(offset),
      corner = Math.max(
        1,
        Math.hypot(Math.max(point[0], size[0] - point[0]), Math.max(point[1], size[1] - point[1])),
      ),
      radius =
        fragmentClamp(Math.max(0, distance - config.pin_radius) / corner, 0, 1) **
        config.distance_exponent,
      wave = fragmentClamp(Math.floor(radius * config.batches) / config.batches, 0, 1),
      jitter = (fragmentHash(cell.id, 1) * 2 - 1) * config.delay_jitter,
      delay =
        (config.delay_near_ms + (config.delay_far_ms - config.delay_near_ms) * wave) * (1 + jitter),
      response =
        config.response_near_ms + (config.response_far_ms - config.response_near_ms) * radius;
    cell.delay = Math.round(fragmentClamp(delay, 0, 600) * 1e6) / 1e6;
    cell.response = fragmentClamp(
      response * (1 + (fragmentHash(cell.id, 2) * 2 - 1) * config.response_jitter),
      20,
      800,
    );
    cell.pinTarget =
      Math.hypot(
        Math.max(0, Math.abs(offset[0]) - cell.half),
        Math.max(0, Math.abs(offset[1]) - cell.half),
      ) <= config.pin_radius;
    cell.radial = fragmentScale(
      fragmentScale(offset, 1 / Math.max(distance, 1)),
      Math.sqrt(radius),
    );
    const angle = fragmentHash(cell.id, 3) * 2 * Math.PI;
    cell.axis =
      config.rotation_mode === "movement"
        ? [-cell.radial[1], cell.radial[0]]
        : config.rotation_mode === "random"
          ? [Math.cos(angle), Math.sin(angle)]
          : [0, 0];
    if (fresh) cell.pin.finish([cell.pinTarget ? 1 : 0, 0]);
  }
  // Native BTreeMap ordering is lexicographic (x, y), including when pin weights
  // tie in the renderer. Keep this order for deterministic overlapping pieces.
  for (let x = first[0]; x < last[0]; x++)
    for (let y = first[1]; y < last[1]; y++) {
      const cell = {
        id: [x, y],
        center: [origin[0] + (x + 0.5) * tile, origin[1] + (y + 0.5) * tile],
        half: tile * 0.5,
        position: fragmentSpring(),
        spread: fragmentSpring(),
        rotation: fragmentSpring(),
        tilt: fragmentSpring(),
        pin: fragmentSpring(),
      };
      configure(cell, true);
      cells.push(cell);
    }
  function targetAt(at) {
    let low = 0,
      high = history.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (history[middle].at <= at) low = middle + 1;
      else high = middle;
    }
    return history[Math.max(0, low - 1)].position;
  }
  function envelope(now) {
    if (releasedAt === null) return [1, 0];
    const duration = config.release_ms / 1000,
      taper = Math.min(duration, 0.4),
      t = fragmentClamp((Math.max(0, now - releasedAt) / 1000 - (duration - taper)) / taper, 0, 1);
    return [1 - t ** 3 * (10 - 15 * t + 6 * t * t), (-30 * t * t * (1 - t) * (1 - t)) / taper];
  }
  function cellAdvance(cell, at, dt, linear = false, end = 0) {
    const spread = fragmentScale(cell.radial, held ? config.press_spread : 0);
    if (linear) {
      let cursor = at,
        goal = targetAt(at - cell.delay);
      for (const event of history) {
        const due = event.at + cell.delay;
        if (due <= at || due >= end) continue;
        cell.position.advance(goal, (due - cursor) / 1000, cell.response);
        cursor = due;
        goal = event.position;
      }
      cell.position.advance(goal, (end - cursor) / 1000, cell.response);
    } else cell.position.advance(targetAt(at - cell.delay), dt, cell.response);
    if (cell.pin.value[0] === 1 && cell.pinTarget) cell.position.finish(target);
    cell.pin.advance([cell.pinTarget ? 1 : 0, 0], dt, 80);
    cell.spread.advance(spread, dt, config.press_response_ms);
    if (linear) {
      cell.rotation.advance([0, 0], dt, config.rotation_response_ms);
      cell.tilt.advance([0, 0], dt, config.rotation_response_ms);
      return;
    }
    const velocity = fragmentAdd(cell.position.velocity, cell.spread.velocity),
      speed = fragmentNorm(velocity),
      denominator = Math.sqrt(speed * speed + config.rotation_speed * config.rotation_speed),
      signed = (velocity[0] * cell.axis[0] + velocity[1] * cell.axis[1]) / denominator;
    cell.rotation.advance(
      [signed * config.rotation_degrees * (Math.PI / 180), 0],
      dt,
      config.rotation_response_ms,
    );
    cell.tilt.advance(
      fragmentScale([-velocity[1], velocity[0]], config.tilt / denominator),
      dt,
      config.rotation_response_ms,
    );
  }
  function pending(at) {
    return (
      history.length > 1 &&
      at <
        history.at(-1).at +
          Math.round(Math.min(config.delay_far_ms * (1 + config.delay_jitter), 600) * 1e6) / 1e6
    );
  }
  function stationary(at) {
    return (
      !pending(at) &&
      cells.every(
        (cell) =>
          fragmentEqual(cell.position.value, target) &&
          fragmentEqual(cell.position.velocity, [0, 0]) &&
          fragmentEqual(
            cell.spread.value,
            fragmentScale(cell.radial, held ? config.press_spread : 0),
          ) &&
          fragmentEqual(cell.spread.velocity, [0, 0]) &&
          fragmentEqual(cell.rotation.value, [0, 0]) &&
          fragmentEqual(cell.rotation.velocity, [0, 0]) &&
          fragmentEqual(cell.tilt.value, [0, 0]) &&
          fragmentEqual(cell.tilt.velocity, [0, 0]) &&
          fragmentEqual(cell.pin.value, [cell.pinTarget ? 1 : 0, 0]) &&
          fragmentEqual(cell.pin.velocity, [0, 0]),
      )
    );
  }
  function advance(now) {
    now = fragmentTime(now);
    if (now <= sampledAt) return;
    if (releasedAt !== null && now - releasedAt >= config.release_ms) {
      for (const cell of cells) {
        cell.position.finish(target);
        for (const spring of [cell.spread, cell.rotation, cell.tilt]) spring.finish([0, 0]);
      }
    } else {
      let cursor = sampledAt;
      if (now - cursor > 2000) {
        const recent = now - 2000;
        for (const cell of cells) cellAdvance(cell, cursor, (recent - cursor) / 1000, true, recent);
        cursor = recent;
        if (stationary(cursor)) {
          sampledAt = now;
          return;
        }
      }
      while (cursor < now) {
        const next = Math.min(cursor + 4, now);
        for (const cell of cells) cellAdvance(cell, cursor, (next - cursor) / 1000);
        cursor = next;
      }
    }
    sampledAt = now;
  }
  function moving() {
    if (releasedAt !== null && sampledAt - releasedAt >= config.release_ms) return false;
    if (pending(sampledAt)) return true;
    return cells.some(
      (cell) =>
        fragmentNorm(fragmentSub(cell.position.value, target)) > 0.001 ||
        fragmentNorm(cell.position.velocity) > 0.01 ||
        fragmentNorm(
          fragmentSub(
            cell.spread.value,
            fragmentScale(cell.radial, held ? config.press_spread : 0),
          ),
        ) > 0.001 ||
        fragmentNorm(cell.spread.velocity) > 0.01 ||
        fragmentNorm(cell.rotation.value) > 0.0001 ||
        fragmentNorm(cell.rotation.velocity) > 0.001 ||
        fragmentNorm(cell.tilt.value) > 0.0001 ||
        fragmentNorm(cell.tilt.velocity) > 0.001,
    );
  }
  function resume(now) {
    if (releasedAt === null) return;
    const [e, d] = envelope(now);
    for (const cell of cells) {
      const lag = fragmentLimited(fragmentSub(cell.position.value, target), config.max_lag);
      cell.position.value = fragmentAdd(target, fragmentScale(lag, e));
      cell.position.velocity = fragmentAdd(
        fragmentScale(cell.position.velocity, e),
        fragmentScale(lag, d),
      );
      for (const spring of [cell.spread, cell.rotation, cell.tilt]) {
        spring.velocity = fragmentAdd(
          fragmentScale(spring.velocity, e),
          fragmentScale(spring.value, d),
        );
        spring.value = fragmentScale(spring.value, e);
      }
    }
    releasedAt = null;
  }
  function grab(nextAnchor, now) {
    const next = fragmentPoint(nextAnchor);
    now = fragmentTime(now);
    advance(now);
    resume(now);
    held = true;
    anchor = next;
    const fresh = !moving();
    for (const cell of cells) configure(cell, fresh);
  }
  function push(delta, now) {
    // Native rejects invalid device deltas before advancing its clock.
    if (!Array.isArray(delta) || delta.length !== 2 || !delta.every(Number.isFinite)) return;
    now = fragmentTime(now);
    advance(now);
    if (fragmentEqual(delta, [0, 0])) return;
    resume(now);
    target = fragmentAdd(
      target,
      delta.map((value) => fragmentClamp(value, -1e6, 1e6)),
    );
    if (history.length > 1 && Math.floor(history.at(-1).at / 4) === Math.floor(now / 4))
      history.at(-1).position = [...target];
    else history.push({ at: now, position: [...target] });
    const cutoff = Math.max(0, now - 608);
    let keep = 0;
    while (keep < history.length && history[keep].at < cutoff) keep++;
    history.splice(0, Math.max(0, keep - 1));
    if (history.length > 256) history.splice(0, history.length - 256);
  }
  function release(now) {
    now = fragmentTime(now);
    advance(now);
    held = false;
    releasedAt ??= now;
  }
  function sample(now) {
    now = fragmentTime(now);
    advance(now);
    const e = envelope(now)[0];
    return {
      size: [...size],
      target: [...target],
      anchor: [...anchor],
      held,
      released: releasedAt !== null,
      moving: moving(),
      max_lag: config.max_lag,
      cells: cells.map((cell) => {
        const pin = fragmentClamp(cell.pin.value[0], 0, 1),
          factor = (1 - pin) * e,
          translation = fragmentScale(
            fragmentAdd(
              fragmentLimited(fragmentSub(cell.position.value, target), config.max_lag),
              cell.spread.value,
            ),
            factor,
          ),
          speed =
            fragmentNorm(fragmentAdd(cell.position.velocity, cell.spread.velocity)) +
            fragmentNorm(cell.rotation.velocity) * cell.half;
        return {
          center: cell.center.map(Math.fround),
          half_extent: [Math.fround(cell.half), Math.fround(cell.half)],
          translation: translation.map(Math.fround),
          rotation: Math.fround(cell.rotation.value[0] * factor),
          tilt: fragmentScale(cell.tilt.value, factor).map(Math.fround),
          edge_blend: Math.fround(fragmentClamp(speed / 48, 0, 1)),
          pin_weight: Math.fround(pin),
        };
      }),
    };
  }
  return Object.freeze({ grab, push, release, sample });
}

function createFragmentDemo(config, options = {}) {
  const settings = { ...config },
    geometry = structuredClone(options),
    dragMs = 1600,
    durationMs = dragMs + settings.release_ms,
    events = [];
  // A press/hold, forward drag, pause and reversal share a fixed 125Hz input
  // clock. Seeking reconstructs that clock, independent of render cadence.
  const waypoints = [
    [0, 0, 0],
    [240, 0, 0],
    [640, 150, 42],
    [840, 150, 42],
    [1280, -110, -32],
    [1600, 0, 0],
  ];
  let previous = [0, 0];
  for (let at = 8; at <= dragMs; at += 8) {
    let segment = 0;
    while (segment + 2 < waypoints.length && at > waypoints[segment + 1][0]) segment++;
    const from = waypoints[segment],
      to = waypoints[segment + 1],
      t = (at - from[0]) / (to[0] - from[0]),
      position = [from[1] + (to[1] - from[1]) * t, from[2] + (to[2] - from[2]) * t];
    events.push({ at, delta: fragmentSub(position, previous) });
    previous = position;
  }
  let motion = null,
    eventIndex = 0,
    sampled = -1,
    released = false;
  function sample(elapsedMs) {
    if (!Number.isFinite(elapsedMs)) throw new Error("Fragment preview time must be finite.");
    const elapsed = fragmentClamp(elapsedMs, 0, durationMs),
      // Use the native 4ms integration boundary. Render cadence cannot create
      // extra fractional integration slices or change the velocity-driven pose.
      at = elapsed === durationMs ? elapsed : Math.floor(elapsed / 4) * 4;
    if (!motion || at < sampled) {
      motion = createFragmentMotion(settings, {
        ...geometry,
        anchor: geometry.anchor || [0.5, 0.12],
        nowMs: 0,
      });
      motion.grab(geometry.anchor || [0.5, 0.12], 0);
      eventIndex = 0;
      released = false;
    }
    while (eventIndex < events.length && events[eventIndex].at <= at) {
      const event = events[eventIndex++];
      motion.push(event.delta, event.at);
    }
    if (at >= dragMs && !released) {
      motion.release(dragMs);
      released = true;
    }
    sampled = at;
    return {
      ...motion.sample(at),
      elapsedMs: elapsed,
      phase: elapsed < dragMs ? "drag" : "settle",
      durationMs,
    };
  }
  // Validate eagerly, including density, even before playback starts.
  createFragmentMotion(settings, geometry);
  return Object.freeze({ durationMs, dragMs, sample });
}

// Native mesh adapter: the texture exactly covers the synthetic window. Source
// UVs and local cell coordinates stay fixed while destination corners move.
function fragmentPreviewMesh(sample) {
  const f = Math.fround,
    size = fragmentPoint(sample.size),
    corners = [
      [-1, -1],
      [1, -1],
      [-1, 1],
      [-1, 1],
      [1, -1],
      [1, 1],
    ],
    vertices = [];
  if (!sample.cells.length || sample.cells.length > 4096 || size.some((value) => value <= 0))
    throw new Error("Invalid fragment mesh geometry.");
  const resting = sample.cells.every(
    (cell) =>
      fragmentEqual(cell.translation, [0, 0]) &&
      cell.rotation === 0 &&
      fragmentEqual(cell.tilt, [0, 0]) &&
      cell.edge_blend === 0,
  );
  if (resting) {
    for (const [x, y] of corners) {
      const u = (x + 1) / 2,
        v = (y + 1) / 2;
      vertices.push(
        u * size[0],
        v * size[1],
        u,
        v,
        (x * size[0]) / 2,
        (y * size[1]) / 2,
        size[0] / 2,
        size[1] / 2,
        0,
      );
    }
  } else
    for (const cell of [...sample.cells].sort((a, b) => a.pin_weight - b.pin_weight)) {
      const sin = f(Math.sin(cell.rotation)),
        cos = f(Math.cos(cell.rotation)),
        sx = f(Math.sin(cell.tilt[0])),
        cx = f(Math.cos(cell.tilt[0])),
        sy = f(Math.sin(cell.tilt[1])),
        cy = f(Math.cos(cell.tilt[1]));
      for (const corner of corners) {
        const local = corner.map((value, axis) => f(value * cell.half_extent[axis])),
          source = local.map((value, axis) => f(cell.center[axis] + value)),
          tilted = [f(f(cy * local[0]) + f(f(sx * sy) * local[1])), f(cx * local[1])],
          rotated = [
            f(f(cos * tilted[0]) - f(sin * tilted[1])),
            f(f(sin * tilted[0]) + f(cos * tilted[1])),
          ],
          position = rotated.map((value, axis) =>
            f(f(cell.center[axis] + cell.translation[axis]) + value),
          );
        vertices.push(
          ...position,
          f(source[0] / f(size[0])),
          f(source[1] / f(size[1])),
          ...local,
          ...cell.half_extent,
          fragmentClamp(cell.edge_blend, 0, 1),
        );
      }
    }
  return new Float32Array(vertices);
}

// Kept token-identical to shaders/fragment-motion.glsl; the unit test checks the
// native material instead of maintaining an independently approximated shader.
const FRAGMENT_PREVIEW_MATERIAL = `
vec4 fragment_motion_mesh_color(vec2 source_uv, vec2 local_px, vec2 half_extent, float edge_blend) {
    if (any(lessThan(source_uv, vec2(0.0))) || any(greaterThanEqual(source_uv, vec2(1.0))))
        return vec4(0.0);
    vec2 edge = half_extent - abs(local_px);
    float coverage = smoothstep(0.0, 0.8 / max(0.01, niri_scale), min(edge.x, edge.y));
    coverage = mix(1.0, coverage, clamp(edge_blend, 0.0, 1.0));
    return texture2D(niri_tex, source_uv) * coverage;
}
`;

function createFragmentRenderer(canvas, textureSource) {
  const gl = canvas.getContext("webgl", {
    alpha: true,
    premultipliedAlpha: true,
    preserveDrawingBuffer: true,
  });
  if (!gl) throw new Error("WebGL is unavailable for the fragment preview.");
  let program,
    buffer,
    texture,
    destroyed = false;
  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const error = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(error || "Fragment preview shader compilation failed.");
    }
    return shader;
  }
  try {
    const vertex = compile(
      gl.VERTEX_SHADER,
      `
      attribute vec2 position; attribute vec4 source; attribute vec3 extra;
      uniform vec2 surface; uniform vec2 origin;
      varying vec2 source_uv; varying vec2 local_px; varying vec2 half_extent; varying float edge_blend;
      void main() {
        vec2 pixel = (position + origin) / surface;
        gl_Position = vec4(pixel.x * 2.0 - 1.0, 1.0 - pixel.y * 2.0, 0.0, 1.0);
        source_uv = source.xy; local_px = source.zw; half_extent = extra.xy; edge_blend = extra.z;
      }`,
    );
    let fragment;
    try {
      fragment = compile(
        gl.FRAGMENT_SHADER,
        `precision highp float;
        uniform sampler2D niri_tex; uniform float niri_scale;
        varying vec2 source_uv; varying vec2 local_px; varying vec2 half_extent; varying float edge_blend;
        ${FRAGMENT_PREVIEW_MATERIAL}
        void main() { gl_FragColor = fragment_motion_mesh_color(source_uv, local_px, half_extent, edge_blend); }`,
      );
      program = gl.createProgram();
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS))
        throw new Error(gl.getProgramInfoLog(program) || "Fragment preview shader linking failed.");
    } finally {
      gl.deleteShader(vertex);
      if (fragment) gl.deleteShader(fragment);
    }
    buffer = gl.createBuffer();
    texture = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, textureSource);
    for (const name of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER])
      gl.texParameteri(gl.TEXTURE_2D, name, gl.LINEAR);
    for (const name of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T])
      gl.texParameteri(gl.TEXTURE_2D, name, gl.CLAMP_TO_EDGE);
  } catch (error) {
    if (program) gl.deleteProgram(program);
    if (buffer) gl.deleteBuffer(buffer);
    if (texture) gl.deleteTexture(texture);
    throw error;
  }
  const attributes = [
    ["position", 2, 0],
    ["source", 4, 2],
    ["extra", 3, 6],
  ].map(([name, size, offset]) => [gl.getAttribLocation(program, name), size, offset]);
  const uniforms = Object.fromEntries(
    ["surface", "origin", "niri_tex", "niri_scale"].map((name) => [
      name,
      gl.getUniformLocation(program, name),
    ]),
  );
  function draw(sample, { offset = sample.target, scale = 1 } = {}) {
    if (destroyed || gl.isContextLost())
      throw new Error("Fragment preview renderer is unavailable.");
    offset = fragmentPoint(offset);
    if (!Number.isFinite(scale) || scale <= 0)
      throw new Error("Fragment preview scale must be positive.");
    const mesh = fragmentPreviewMesh(sample);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, mesh, gl.DYNAMIC_DRAW);
    for (const [attribute, size, start] of attributes) {
      gl.enableVertexAttribArray(attribute);
      gl.vertexAttribPointer(attribute, size, gl.FLOAT, false, 36, start * 4);
    }
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.uniform1i(uniforms.niri_tex, 0);
    gl.uniform1f(uniforms.niri_scale, scale);
    gl.uniform2f(uniforms.surface, canvas.width, canvas.height);
    gl.uniform2f(
      uniforms.origin,
      (canvas.width - sample.size[0]) / 2 + offset[0],
      (canvas.height - sample.size[1]) / 2 + offset[1],
    );
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.TRIANGLES, 0, mesh.length / 9);
    gl.disable(gl.BLEND);
    if (gl.getError() !== gl.NO_ERROR) throw new Error("Fragment preview rendering failed.");
  }
  function destroy() {
    if (destroyed) return;
    destroyed = true;
    gl.deleteBuffer(buffer);
    gl.deleteTexture(texture);
    gl.deleteProgram(program);
  }
  return Object.freeze({ draw, destroy });
}
