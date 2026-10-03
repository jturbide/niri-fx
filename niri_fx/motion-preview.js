// Visual concept only: this is not an installed Niri movement shader.
// Each sprite keeps its own source rectangle and returns to that same rectangle
// at its destination. Two streams can cross without mixing up window contents.
class MotionPreview {
  constructor(canvas, first) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.first = first;
    this.second = document.createElement("canvas");
    this.second.width = 600;
    this.second.height = 380;
    const c = this.second.getContext("2d");
    c.fillStyle = "#352c4d";
    c.fillRect(0, 0, 600, 380);
    c.fillStyle = "#51446c";
    c.fillRect(0, 0, 600, 44);
    c.fillStyle = "#e6d9ff";
    c.font = "14px sans-serif";
    c.fillText("Orbit / another window", 205, 27);
    c.font = "bold 30px sans-serif";
    c.fillText("A different point of view.", 32, 104);
    c.fillStyle = "#baaacc";
    c.font = "16px sans-serif";
    c.fillText("Two windows. One shared choreography.", 32, 138);
    for (let i = 0; i < 3; i++) {
      c.fillStyle = ["#745c86", "#6c598e", "#806d92"][i];
      c.fillRect(32 + i * 182, 175, 170, 112);
      c.fillStyle = "#f0e7ff";
      c.font = "20px sans-serif";
      c.fillText(["Discover", "Connect", "Build"][i], 48 + i * 182, 212);
    }
    c.fillStyle = "#9483ac";
    for (let i = 0; i < 3; i++) c.fillRect(32, 315 + i * 14, 400 - i * 60, 5);
  }
  layout(mode) {
    return mode === "swap"
      ? [
          { x: 65, to: 555, image: this.first, id: 0 },
          { x: 555, to: 65, image: this.second, id: 1 },
        ]
      : [{ x: 65, to: 555, image: this.first, id: 0 }];
  }
  particles(p, mode, parameters, seed) {
    const smooth = (t) => t * t * (3 - 2 * t),
      mix = (a, b, t) => a + (b - a) * t;
    const hash = (n) => {
      const x = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453;
      return x - Math.floor(x);
    };
    const tile = parameters.particles
      ? Math.max(4, Math.sqrt((600 * 380) / parameters.particles))
      : parameters.tile_size;
    const list = [];
    const releaseIndex = (x, y) => {
      if (parameters.release === "together") return 0;
      let axis = x;
      if (parameters.release === "right") axis = 1 - x;
      if (parameters.release === "up") axis = y;
      if (parameters.release === "down") axis = 1 - y;
      if (["center", "edges"].includes(parameters.release)) {
        axis =
          Math.hypot(
            (x - parameters.origin_x) / Math.max(parameters.origin_x, 1 - parameters.origin_x),
            (y - parameters.origin_y) / Math.max(parameters.origin_y, 1 - parameters.origin_y),
          ) / Math.SQRT2;
        if (parameters.release === "edges") axis = 1 - axis;
      }
      if (parameters.release === "diagonal") axis = (x + y) / 2;
      if (parameters.release === "checkerboard")
        return ((Math.floor(x * 6) + Math.floor(y * 6)) % 2) * 2;
      return Math.max(0, Math.min(2, Math.floor(axis * 3)));
    };
    const edge = (index, count, axis) =>
      index <= 0
        ? 0
        : index >= count
          ? count * tile
          : (index + (hash(index + axis) * 2 - 1) * 0.2 * parameters.size_variation) * tile;

    for (const window of this.layout(mode)) {
      for (let row = 0; row < Math.ceil(380 / tile); row++)
        for (let col = 0; col < Math.ceil(600 / tile); col++) {
          const i = row * 1000 + col + window.id * 100000,
            r = hash(i),
            v = hash(i + 37),
            w = hash(i + 101);
          const group = releaseIndex(((col + 0.5) * tile) / 600, ((row + 0.5) * tile) / 380);
          const delay = parameters.stagger * 0.5 * r + group * parameters.wave_span * 0.125,
            u = Math.max(0, Math.min(1, (p - delay) / (1 - 2 * delay))),
            t = smooth(u);
          const wave = Math.sin(Math.PI * t),
            sx = edge(col, Math.ceil(600 / tile), 31),
            sy = edge(row, Math.ceil(380 / tile), 71),
            sw = Math.min(edge(col + 1, Math.ceil(600 / tile), 31), 600) - sx,
            sh = Math.min(edge(row + 1, Math.ceil(380 / tile), 71), 380) - sy;
          // Jitter can put the final cell's lower boundary beyond the texture.
          if (sw <= 0 || sh <= 0) continue;
          const offsetX = (sx + sw / 2 - 300) * 0.633333,
            offsetY = (sy + sh / 2 - 190) * 0.633333;
          const spread = (25 + parameters.scatter * 0.65) * parameters.dispersion;
          let x =
            mix(window.x, window.to, t) +
            190 +
            offsetX * (1 - 0.68 * wave) +
            (r - 0.5) * spread * 2 * wave;
          let y = 370 + offsetY * (1 - 0.45 * wave) + (v - 0.5) * spread * 2 * wave;
          // Opposing arcs cross in the middle: recognizable colors interleave.
          y += (window.id ? 1 : -1) * 42 * Math.sin(2 * Math.PI * t);
          const strength = parameters.gravity_strength * wave;
          if (parameters.gravity === "down") y += 65 * strength;
          if (parameters.gravity === "up") y -= 65 * strength;
          if (parameters.gravity === "left") x -= 65 * strength;
          if (parameters.gravity === "right") x += 65 * strength;
          if (parameters.gravity === "space") {
            x += offsetX * 0.35 * strength;
            y += offsetY * 0.35 * strength;
          }
          if (parameters.gravity === "center") {
            x -= offsetX * 0.25 * strength;
            y -= offsetY * 0.25 * strength;
          }
          const ripple =
            ((parameters.wave_strength * 380 * 0.45) / (2 * Math.PI * parameters.wave_frequency)) *
            Math.sin(
              2 *
                Math.PI *
                ((parameters.wave_frequency * (sy + sh / 2)) / 380 - parameters.wave_speed * t),
            ) *
            wave;
          x += ripple * (window.id ? -1 : 1);
          y += (w - 0.5) * 100 * parameters.direction_variation * wave;
          let angle = 0;
          if (parameters.rotation === "random")
            angle = (((w * 2 - 1) * parameters.spin * Math.PI) / 180) * wave;
          if (parameters.rotation === "gravity")
            angle = (((window.id ? -1 : 1) * Math.min(parameters.spin, 90) * Math.PI) / 180) * wave;
          angle += ((parameters.swirl * Math.PI) / 180) * wave * (r - 0.5);
          list.push({
            x,
            y,
            sx,
            sy,
            sw,
            sh,
            angle,
            scale: 0.633333 * (1 - 0.38 * wave) * (1 - 0.85 * parameters.fragment_shrink * wave),
            roundness: parameters.fragment_roundness * wave,
            image: window.image,
            depth: w,
            id: window.id,
          });
        }
    }
    return list.sort((a, b) => a.depth - b.depth);
  }
  draw(p, mode, parameters, seed) {
    const c = this.ctx;
    c.clearRect(0, 0, 1000, 760);
    c.save();
    c.strokeStyle = "#38495e";
    c.lineWidth = 1;
    c.setLineDash([5, 7]);
    for (const x of [65, 555]) c.strokeRect(x, 250, 380, 240.667);
    c.setLineDash([]);
    c.font = "13px system-ui";
    c.fillStyle = "#95a9c0";
    c.fillText("COLUMN 01", 65, 220);
    c.fillText("COLUMN 02", 555, 220);
    c.textAlign = "center";
    c.fillStyle = "#d3e1f1";
    c.font = "20px system-ui";
    c.fillText(
      mode === "swap" ? "Two streams, one exchange." : "Break apart. Travel. Come together.",
      500,
      125,
    );
    c.font = "14px system-ui";
    c.fillStyle = "#97abc3";
    c.fillText("Movement concept · not active on your desktop", 500, 625);
    c.restore();
    if (p <= 0 || p >= 1) {
      for (const window of this.layout(mode))
        c.drawImage(window.image, p <= 0 ? window.x : window.to, 249.667, 380, 240.667);
      return;
    }
    for (const part of this.particles(p, mode, parameters, seed)) {
      c.save();
      c.translate(part.x, part.y);
      c.rotate(part.angle);
      if (part.roundness > 0) {
        const width = part.sw * part.scale,
          height = part.sh * part.scale;
        c.beginPath();
        c.roundRect(
          -width / 2,
          -height / 2,
          width,
          height,
          Math.min(width, height) * 0.5 * part.roundness,
        );
        c.clip();
      }
      c.drawImage(
        part.image,
        part.sx,
        part.sy,
        part.sw,
        part.sh,
        (-part.sw * part.scale) / 2,
        (-part.sh * part.scale) / 2,
        part.sw * part.scale,
        part.sh * part.scale,
      );
      c.restore();
    }
  }
}
