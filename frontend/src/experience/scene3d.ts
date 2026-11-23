import * as THREE from 'three';

/**
 * Compartments in tray-local coordinates (x/z centre and footprint), matching the dividers
 * in bento.glb. Order = order of the scroll story (01 → 05).
 */
export const COMPARTMENTS = [
  { name: 'cucumbers', x: -0.79, z: 0.75, w: 2.1, d: 1.46 },
  { name: 'sushi', x: 1.075, z: 0.75, w: 1.53, d: 1.46 },
  { name: 'eggs', x: 0.105, z: -0.74, w: 1.0, d: 1.48 },
  { name: 'dango', x: -1.14, z: -0.74, w: 1.4, d: 1.48 },
  { name: 'naruto', x: 1.245, z: -0.74, w: 1.19, d: 1.48 },
] as const;

/** World-space framing targets, written once by BentoModel after the scene mounts. */
export const compartmentTargets: { center: THREE.Vector3; size: number }[] = COMPARTMENTS.map(() => ({
  center: new THREE.Vector3(),
  size: 1,
}));
