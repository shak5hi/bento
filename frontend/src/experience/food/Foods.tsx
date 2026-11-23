import { useMemo } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import {
  cucumberSkinTexture,
  cucumberSliceTexture,
  eggTexture,
  makiTopTexture,
  narutoTexture,
  noriTexture,
  riceTexture,
  rng,
  salmonTexture,
} from './textures';

/* ───────────── geometry helpers ───────────── */

/** Drape a flat slab: lower its ends along `axis` so it sags over whatever is underneath. */
function drape(geo: THREE.BufferGeometry, axis: 'x' | 'z', half: number, amount: number) {
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const t = (axis === 'x' ? pos.getX(i) : pos.getZ(i)) / half;
    pos.setY(i, pos.getY(i) - amount * t * t);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  return geo;
}

/**
 * A finely subdivided slab (so it can bend) whose top edges are softened into a pillow shape.
 * RoundedBoxGeometry can't be draped: its flat faces have no interior vertices.
 */
function slab(w: number, h: number, d: number, soften: number) {
  const geo = new THREE.BoxGeometry(w, h, d, 32, 2, 16);
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    if (y <= 0) continue;
    const e = Math.max(Math.abs(pos.getX(i)) / (w / 2), Math.abs(pos.getZ(i)) / (d / 2));
    const k = THREE.MathUtils.smoothstep(e, 0.55, 1);
    pos.setY(i, y - soften * k * k);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  return geo;
}

/** Narrow a slab toward its ends (along x), like a slice of fish. */
function taper(geo: THREE.BufferGeometry, half: number, amount: number) {
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) {
    const t = pos.getX(i) / half;
    pos.setZ(i, pos.getZ(i) * (1 - amount * t * t));
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  return geo;
}

/** Gently squeeze and roughen a geometry so food doesn't look machine-made. */
function organic(geo: THREE.BufferGeometry, strength: number, seed: number) {
  const pos = geo.attributes.position as THREE.BufferAttribute;
  const r = rng(seed);
  const a = r() * 6, b = r() * 6, c = r() * 6;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const n = Math.sin(x * 9 + a) * Math.sin(y * 7 + b) * Math.sin(z * 8 + c);
    const k = 1 + n * strength;
    pos.setXYZ(i, x * k, y * k, z * k);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  return geo;
}

function ruffledDisc(radius: number, depth: number, lobes: number) {
  const shape = new THREE.Shape();
  const steps = lobes * 12;
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    const r = radius * (1 + 0.065 * Math.cos(a * lobes));
    const x = Math.cos(a) * r, y = Math.sin(a) * r;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  }
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelThickness: 0.012, bevelSize: 0.012, bevelSegments: 3, curveSegments: 4 });
  geo.translate(0, 0, -depth / 2);
  geo.rotateX(-Math.PI / 2);
  return geo;
}

function leafGeometry(length: number, width: number) {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.quadraticCurveTo(width, length * 0.45, 0, length);
  s.quadraticCurveTo(-width, length * 0.45, 0, 0);
  const geo = new THREE.ShapeGeometry(s, 16);
  geo.rotateX(-Math.PI / 2);
  // fold along the midrib
  const pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < pos.count; i++) pos.setY(i, Math.abs(pos.getX(i)) * 0.35);
  geo.computeVertexNormals();
  return geo;
}

/* ───────────── shared materials (built once) ───────────── */

function useMaterials() {
  return useMemo(() => {
    const rice = riceTexture();
    const salmon = salmonTexture();
    const nori = noriTexture();
    const naruto = narutoTexture().clone();
    naruto.repeat.set(1 / 0.5, 1 / 0.5); // shape coords span ±0.25
    naruto.offset.set(0.5, 0.5);
    naruto.needsUpdate = true;

    return {
      rice: new THREE.MeshStandardMaterial({ map: rice, bumpMap: rice, bumpScale: 0.6, roughness: 0.85 }),
      salmon: new THREE.MeshPhysicalMaterial({ map: salmon, roughness: 0.32, clearcoat: 0.6, clearcoatRoughness: 0.25, sheen: 0.4, sheenColor: new THREE.Color('#ffd2b8') }),
      nori: new THREE.MeshStandardMaterial({ map: nori, roughness: 0.7 }),
      makiTop: new THREE.MeshStandardMaterial({ map: makiTopTexture(), roughness: 0.6 }),
      cucumberSkin: new THREE.MeshPhysicalMaterial({ map: cucumberSkinTexture(), roughness: 0.38, clearcoat: 0.5, clearcoatRoughness: 0.3 }),
      cucumberFlesh: new THREE.MeshPhysicalMaterial({ map: cucumberSliceTexture(), roughness: 0.25, clearcoat: 0.8, clearcoatRoughness: 0.15 }),
      cucumberRim: new THREE.MeshStandardMaterial({ color: '#2f6a1f', roughness: 0.4 }),
      eggWhite: new THREE.MeshPhysicalMaterial({ color: '#fbf8f1', roughness: 0.28, clearcoat: 0.35 }),
      eggFace: new THREE.MeshPhysicalMaterial({ map: eggTexture(), roughness: 0.3, clearcoat: 0.5 }),
      chive: new THREE.MeshStandardMaterial({ color: '#3f7d24', roughness: 0.5 }),
      dangoPink: new THREE.MeshPhysicalMaterial({ color: '#f4a3b8', roughness: 0.55, sheen: 0.6, sheenColor: new THREE.Color('#ffe3ec') }),
      dangoWhite: new THREE.MeshPhysicalMaterial({ color: '#f6efe4', roughness: 0.55, sheen: 0.6, sheenColor: new THREE.Color('#ffffff') }),
      dangoGreen: new THREE.MeshPhysicalMaterial({ color: '#86b24f', roughness: 0.55, sheen: 0.5, sheenColor: new THREE.Color('#dff2c0') }),
      stick: new THREE.MeshStandardMaterial({ color: '#d8b273', roughness: 0.7 }),
      narutoFace: new THREE.MeshStandardMaterial({ map: naruto, roughness: 0.45 }),
      narutoEdge: new THREE.MeshStandardMaterial({ color: '#f1a7b6', roughness: 0.5 }),
      leaf: new THREE.MeshPhysicalMaterial({ color: '#4f8f2a', roughness: 0.35, clearcoat: 0.6, side: THREE.DoubleSide }),
    };
  }, []);
}

type Mats = ReturnType<typeof useMaterials>;

/* ───────────── compartment 1 · cucumbers ───────────── */

function Cucumbers({ m, floor }: { m: Mats; floor: number }) {
  const skin = useMemo(() => {
    const g = new THREE.CapsuleGeometry(0.15, 0.95, 8, 24);
    g.rotateZ(Math.PI / 2);
    return organic(g, 0.035, 3);
  }, []);
  const slice = useMemo(() => new THREE.CylinderGeometry(0.2, 0.2, 0.05, 40), []);

  const r = rng(101);
  const wholes = [0.33, 0.73, 1.13].map((z, i) => ({ z, x: -1.2 + (r() - 0.5) * 0.12, yaw: (r() - 0.5) * 0.18, i }));
  const slices: { p: [number, number, number]; rot: [number, number, number] }[] = [];
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 2; col++) {
      slices.push({
        p: [-0.42 + col * 0.42 + (r() - 0.5) * 0.04, floor + 0.17 + col * 0.02, 0.24 + row * 0.33],
        rot: [-0.55 + (r() - 0.5) * 0.12, (r() - 0.5) * 0.4, (r() - 0.5) * 0.15],
      });
    }
  }
  // a few slices resting on top of the whole cucumbers
  slices.push({ p: [-1.45, floor + 0.34, 0.52], rot: [-0.15, 0.3, 0.12] }, { p: [-0.98, floor + 0.35, 0.95], rot: [0.12, -0.2, -0.1] });

  return (
    <group>
      {wholes.map((c) => (
        <mesh key={c.i} geometry={skin} material={m.cucumberSkin} position={[c.x, floor + 0.15, c.z]} rotation={[0, c.yaw, 0]} castShadow receiveShadow />
      ))}
      {slices.map((s, i) => (
        <mesh key={i} geometry={slice} material={[m.cucumberRim, m.cucumberFlesh, m.cucumberFlesh]} position={s.p} rotation={s.rot} castShadow receiveShadow />
      ))}
    </group>
  );
}

/* ───────────── compartment 2 · salmon nigiri + maki ───────────── */

function Nigiri({ m, position, yaw }: { m: Mats; position: [number, number, number]; yaw: number }) {
  const geos = useMemo(() => {
    const rice = organic(new RoundedBoxGeometry(0.6, 0.17, 0.28, 4, 0.08), 0.03, 7);
    const fish = drape(taper(slab(0.7, 0.07, 0.36, 0.045), 0.35, 0.26), 'x', 0.35, 0.08);
    const band = drape(slab(0.1, 0.018, 0.42, 0.006), 'z', 0.21, 0.12);
    return { rice, fish, band };
  }, []);
  return (
    <group position={position} rotation={[0, yaw, 0]}>
      <mesh geometry={geos.rice} material={m.rice} position={[0, 0.085, 0]} castShadow receiveShadow />
      <mesh geometry={geos.fish} material={m.salmon} position={[0, 0.215, 0]} castShadow receiveShadow />
      <mesh geometry={geos.band} material={m.nori} position={[0.02, 0.262, 0]} castShadow />
    </group>
  );
}

function Maki({ m, position }: { m: Mats; position: [number, number, number] }) {
  const geo = useMemo(() => new THREE.CylinderGeometry(0.17, 0.17, 0.2, 40), []);
  return <mesh geometry={geo} material={[m.nori, m.makiTop, m.nori]} position={position} castShadow receiveShadow />;
}

function Sushi({ m, floor }: { m: Mats; floor: number }) {
  const r = rng(202);
  const nigiri: [number, number][] = [[0.72, 0.27], [1.42, 0.27], [0.72, 0.62], [1.42, 0.62], [1.42, 0.98]];
  return (
    <group>
      {nigiri.map(([x, z], i) => (
        <Nigiri key={i} m={m} position={[x, floor, z]} yaw={(r() - 0.5) * 0.12} />
      ))}
      <Maki m={m} position={[0.55, floor + 0.1, 1.05]} />
      <Maki m={m} position={[0.93, floor + 0.1, 1.08]} />
      <Leaf m={m} position={[1.25, floor + 0.05, 1.33]} rotation={[0, 1.9, 0]} scale={1.1} />
      <Leaf m={m} position={[0.6, floor + 0.04, 1.36]} rotation={[0, -1.4, 0]} scale={0.8} />
    </group>
  );
}

/* ───────────── compartment 3 · halved eggs tied with chives ───────────── */

const EGG_ROWS = [-1.2, -0.74, -0.28];
const EGG_COLS = [-0.14, 0.36];

function Eggs({ m, floor }: { m: Mats; floor: number }) {
  const geos = useMemo(() => {
    const dome = new THREE.SphereGeometry(0.2, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2);
    dome.rotateX(Math.PI);
    dome.scale(1, 0.75, 1.3);
    const face = new THREE.CircleGeometry(0.2, 48);
    face.rotateX(-Math.PI / 2);
    face.scale(1, 1, 1.3);
    const bed = organic(new RoundedBoxGeometry(0.94, 0.08, 1.42, 3, 0.03), 0.02, 9);
    return { dome, face, bed };
  }, []);
  const lift = floor + 0.08 + 0.15;
  const chives = useMemo(
    () =>
      EGG_ROWS.map((z, i) => {
        const pts = [
          new THREE.Vector3(-0.38, lift - 0.06, z + 0.03),
          new THREE.Vector3(-0.14, lift + 0.03, z - 0.02),
          new THREE.Vector3(0.11, lift - 0.02, z + 0.04),
          new THREE.Vector3(0.36, lift + 0.03, z - 0.01),
          new THREE.Vector3(0.6, lift - 0.06, z + 0.02 + i * 0.01),
        ];
        return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 48, 0.012, 8, false);
      }),
    [lift],
  );
  return (
    <group>
      <mesh geometry={geos.bed} material={m.rice} position={[0.105, floor + 0.04, -0.74]} receiveShadow />
      {EGG_ROWS.flatMap((z, ri) =>
        EGG_COLS.map((x, ci) => (
          <group key={`${ri}-${ci}`} position={[x, lift, z]} rotation={[0, (ri + ci) % 2 ? 0.12 : -0.1, 0]}>
            <mesh geometry={geos.dome} material={m.eggWhite} castShadow receiveShadow />
            <mesh geometry={geos.face} material={m.eggFace} position={[0, 0.001, 0]} receiveShadow />
          </group>
        )),
      )}
      {chives.map((g, i) => (
        <mesh key={i} geometry={g} material={m.chive} castShadow />
      ))}
    </group>
  );
}

/* ───────────── compartment 4 · dango skewers ───────────── */

function Dango({ m, floor }: { m: Mats; floor: number }) {
  const ball = useMemo(() => organic(new THREE.SphereGeometry(0.15, 32, 24), 0.02, 5).scale(1, 0.92, 1), []);
  const stick = useMemo(() => new THREE.CylinderGeometry(0.014, 0.014, 1.25, 10).rotateZ(Math.PI / 2), []);
  const r = rng(404);
  const rows = [-1.24, -0.88, -0.52, -0.16];
  return (
    <group>
      {rows.map((z, i) => (
        <group key={i} position={[-1.13 + (r() - 0.5) * 0.06, floor + 0.14, z]} rotation={[0, (r() - 0.5) * 0.14, 0]}>
          <mesh geometry={stick} material={m.stick} position={[0.08, 0, 0]} castShadow />
          <mesh geometry={ball} material={m.dangoPink} position={[-0.39, 0, 0]} castShadow receiveShadow />
          <mesh geometry={ball} material={m.dangoWhite} position={[-0.1, 0, 0]} castShadow receiveShadow />
          <mesh geometry={ball} material={m.dangoGreen} position={[0.19, 0, 0]} castShadow receiveShadow />
        </group>
      ))}
      <Leaf m={m} position={[-0.55, floor + 0.03, -0.05]} rotation={[0, 2.6, 0]} scale={0.7} />
    </group>
  );
}

/* ───────────── compartment 5 · naruto fish cakes ───────────── */

function Naruto({ m, floor }: { m: Mats; floor: number }) {
  const disc = useMemo(() => ruffledDisc(0.24, 0.07, 16), []);
  const r = rng(505);
  const spots: [number, number][] = [[0.95, -1.18], [1.52, -1.16], [0.96, -0.72], [1.53, -0.7], [0.97, -0.27], [1.54, -0.25]];
  return (
    <group>
      {spots.map(([x, z], i) => (
        <mesh
          key={i}
          geometry={disc}
          material={[m.narutoFace, m.narutoEdge]}
          position={[x, floor + 0.13 + (i % 2) * 0.01, z]}
          rotation={[-0.42, (r() - 0.5) * 0.5, (r() - 0.5) * 0.08]}
          castShadow
          receiveShadow
        />
      ))}
      <Leaf m={m} position={[1.25, floor + 0.06, -0.48]} rotation={[0, 0.5, 0]} scale={0.85} />
      <Leaf m={m} position={[1.72, floor + 0.05, -0.04]} rotation={[0, -2.2, 0]} scale={0.7} />
    </group>
  );
}

/* ───────────── garnish ───────────── */

function Leaf({ m, position, rotation, scale = 1 }: { m: Mats; position: [number, number, number]; rotation: [number, number, number]; scale?: number }) {
  const geo = useMemo(() => leafGeometry(0.42, 0.13), []);
  return <mesh geometry={geo} material={m.leaf} position={position} rotation={rotation} scale={scale} castShadow receiveShadow />;
}

/* ───────────── the whole lunch ───────────── */

/** Tray-local coordinates: compartment floor sits at y = FLOOR. */
export const FLOOR = -0.29;

export function FoodItems() {
  const m = useMaterials();
  return (
    <group name="FoodItems">
      <Cucumbers m={m} floor={FLOOR} />
      <Sushi m={m} floor={FLOOR} />
      <Eggs m={m} floor={FLOOR} />
      <Dango m={m} floor={FLOOR} />
      <Naruto m={m} floor={FLOOR} />
    </group>
  );
}
