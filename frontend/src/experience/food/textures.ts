import * as THREE from 'three';

/**
 * Procedural food textures, drawn once on canvases (no image downloads).
 * Each generator is memoised: every nigiri shares one salmon texture, etc.
 */

const cache = new Map<string, THREE.CanvasTexture>();

/** Deterministic PRNG so the food looks identical on every load. */
export function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function make(key: string, w: number, h: number, draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, color = true) {
  const hit = cache.get(key);
  if (hit) return hit;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  draw(ctx, w, h);
  const tex = new THREE.CanvasTexture(canvas);
  if (color) tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  cache.set(key, tex);
  return tex;
}

function speckle(ctx: CanvasRenderingContext2D, w: number, h: number, n: number, color: string, size: [number, number], seed: number) {
  const r = rng(seed);
  ctx.fillStyle = color;
  for (let i = 0; i < n; i++) {
    const s = size[0] + r() * (size[1] - size[0]);
    ctx.beginPath();
    ctx.ellipse(r() * w, r() * h, s, s * (0.4 + r() * 0.4), r() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
}

/** Salmon: warm orange with soft white fat lines running diagonally. */
export const salmonTexture = () =>
  make('salmon', 512, 256, (ctx, w, h) => {
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#ff8a4c');
    g.addColorStop(0.5, '#f5743a');
    g.addColorStop(1, '#ff9a5c');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.lineCap = 'round';
    for (let i = -6; i < 16; i++) {
      const x = i * 44;
      ctx.strokeStyle = 'rgba(255, 236, 222, 0.78)';
      ctx.lineWidth = 7;
      ctx.beginPath();
      ctx.moveTo(x, -10);
      ctx.bezierCurveTo(x + 40, h * 0.3, x + 10, h * 0.7, x + 70, h + 10);
      ctx.stroke();
      ctx.strokeStyle = 'rgba(255, 210, 180, 0.35)';
      ctx.lineWidth = 16;
      ctx.stroke();
    }
  });

/** Rice: off-white with tiny grains (used as colour and bump map). */
export const riceTexture = () =>
  make('rice', 256, 256, (ctx, w, h) => {
    ctx.fillStyle = '#f6f2e8';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, 900, 'rgba(214, 205, 186, 0.55)', [4, 7], 11);
    speckle(ctx, w, h, 700, 'rgba(255, 255, 255, 0.95)', [3, 6], 12);
  });

/** Nori: dark green-black sheet with faint fibres. */
export const noriTexture = () =>
  make('nori', 256, 256, (ctx, w, h) => {
    ctx.fillStyle = '#1c231b';
    ctx.fillRect(0, 0, w, h);
    speckle(ctx, w, h, 500, 'rgba(70, 92, 60, 0.35)', [2, 6], 21);
    speckle(ctx, w, h, 200, 'rgba(0, 0, 0, 0.4)', [3, 8], 22);
  });

/** Cut maki roll seen from the top: nori ring, rice, colourful filling. */
export const makiTopTexture = () =>
  make('maki', 256, 256, (ctx, w) => {
    const c = w / 2;
    ctx.fillStyle = '#1c231b';
    ctx.beginPath();
    ctx.arc(c, c, c, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#f7f3ea';
    ctx.beginPath();
    ctx.arc(c, c, c * 0.88, 0, Math.PI * 2);
    ctx.fill();
    ctx.save();
    ctx.clip();
    speckle(ctx, w, w, 260, 'rgba(210, 200, 180, 0.6)', [4, 7], 31);
    ctx.restore();
    // filling
    const pieces: [string, number, number, number, number][] = [
      ['#f5743a', -0.22, -0.18, 0.26, 0.2],
      ['#7cb342', 0.08, -0.22, 0.2, 0.18],
      ['#c5e1a5', 0.1, 0.04, 0.2, 0.18],
      ['#ffd54f', -0.24, 0.06, 0.24, 0.16],
    ];
    for (const [col, x, y, pw, ph] of pieces) {
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.roundRect(c + x * w, c + y * w, pw * w, ph * w, 8);
      ctx.fill();
    }
  });

/** Cucumber skin: dark green with paler lengthwise stripes. */
export const cucumberSkinTexture = () =>
  make('cucumber-skin', 256, 256, (ctx, w, h) => {
    ctx.fillStyle = '#2f6a1f';
    ctx.fillRect(0, 0, w, h);
    const r = rng(41);
    for (let x = 0; x < w; x += 18) {
      ctx.fillStyle = `rgba(118, 168, 72, ${0.35 + r() * 0.3})`;
      ctx.fillRect(x + r() * 6, 0, 5 + r() * 5, h);
    }
    speckle(ctx, w, h, 160, 'rgba(200, 230, 150, 0.5)', [1.5, 3], 42);
  });

/** Cucumber slice face: pale flesh, dark rim, three-lobed seed pattern. */
export const cucumberSliceTexture = () =>
  make('cucumber-slice', 256, 256, (ctx, w) => {
    const c = w / 2;
    ctx.fillStyle = '#2f6a1f';
    ctx.beginPath();
    ctx.arc(c, c, c, 0, Math.PI * 2);
    ctx.fill();
    const g = ctx.createRadialGradient(c, c, 4, c, c, c * 0.93);
    g.addColorStop(0, '#c9e59a');
    g.addColorStop(0.7, '#e3f3c2');
    g.addColorStop(1, '#b6d97a');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(c, c, c * 0.92, 0, Math.PI * 2);
    ctx.fill();
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2 - Math.PI / 2;
      ctx.save();
      ctx.translate(c + Math.cos(a) * c * 0.3, c + Math.sin(a) * c * 0.3);
      ctx.rotate(a);
      ctx.fillStyle = 'rgba(175, 205, 120, 0.9)';
      ctx.beginPath();
      ctx.ellipse(0, 0, c * 0.26, c * 0.14, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(250, 255, 235, 0.95)';
      for (let s = -2; s <= 2; s++) {
        ctx.beginPath();
        ctx.ellipse(s * c * 0.08, 0, c * 0.03, c * 0.05, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  });

/** Naruto (fish cake) face: white with a pink spiral. */
export const narutoTexture = () =>
  make('naruto', 512, 512, (ctx, w) => {
    const c = w / 2;
    ctx.fillStyle = '#fdf6f3';
    ctx.fillRect(0, 0, w, w);
    ctx.strokeStyle = '#e8577b';
    ctx.lineWidth = 26;
    ctx.lineCap = 'round';
    ctx.beginPath();
    for (let t = 0; t <= Math.PI * 5.2; t += 0.04) {
      const r = 8 + t * 13;
      const x = c + Math.cos(t) * r;
      const y = c + Math.sin(t) * r;
      if (t === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

/** Halved boiled egg face: white with a glossy yolk. */
export const eggTexture = () =>
  make('egg', 256, 256, (ctx, w) => {
    const c = w / 2;
    ctx.fillStyle = '#fbf8f1';
    ctx.fillRect(0, 0, w, w);
    const g = ctx.createRadialGradient(c - 10, c - 14, 6, c, c, c * 0.5);
    g.addColorStop(0, '#ffe27a');
    g.addColorStop(0.65, '#f7b928');
    g.addColorStop(1, '#ec9f1c');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(c, c, c * 0.48, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(236, 200, 120, 0.5)';
    ctx.lineWidth = 6;
    ctx.stroke();
  });
