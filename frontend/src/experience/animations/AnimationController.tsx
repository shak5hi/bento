import { useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { heroScroll } from '../scrollState';
import { compartmentTargets } from '../scene3d';

/*
 * Camera direction:
 *   intro   — 3/4 hero shot → centred top-down (heroScroll.cameraProgress)
 *   opening — one continuous eased spline while the lid comes off (heroScroll.rawProgress)
 *   close-ups — computed 3/4 shots of each compartment, framed on the side of the screen
 *               opposite that chapter's text, whatever the viewport size.
 */

// Hand-picked framing from the original Blender camera.
const P1 = new THREE.Vector3(19.275, 25.827, 13.35);
const Q1 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.094, 0.585, 0.819));
const P2 = new THREE.Vector3(1.025, 34.861, 0.688);
const Q2 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.551, 0.029, 0.979));
const P3 = new THREE.Vector3(1.901, 34.709, 2.912);
const Q3 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.487, 0.055, 0.576));
const P4 = new THREE.Vector3(0.745, 17.841, 1.343);
const Q4 = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.496, 0.042, 0.505));

const openingPath = new THREE.CatmullRomCurve3([P2, P3, P4], false, 'centripetal');

/** Close-up angle: the top-down camera tilted back ~32° so food reads in 3D. */
const Q_CLOSE = Q4.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.56));

/** Where each compartment should sit on screen (viewport fraction), opposite its chapter text. */
const SCREEN_SPOT: [number, number][] = [
  [0.31, 0.45], // 01 text bottom-right → food left
  [0.69, 0.56], // 02 text top-left     → food right
  [0.31, 0.45],
  [0.69, 0.56],
  [0.31, 0.45],
];
/** Fraction of the viewport height the compartment should fill. */
const FILL = 0.78;

const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function AnimationController() {
  const { camera, gl } = useThree();
  const tmp = useMemo(
    () => ({
      pos: new THREE.Vector3(),
      quat: new THREE.Quaternion(),
      fwd: new THREE.Vector3(),
      right: new THREE.Vector3(),
      up: new THREE.Vector3(),
      close: new THREE.Vector3(),
    }),
    [],
  );

  useFrame(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const { pos, quat } = tmp;

    if (heroScroll.rawProgress > 0) {
      const t = easeInOutCubic(heroScroll.rawProgress);
      pos.copy(openingPath.getPoint(t));
      // piecewise slerp with matched speeds at the joint (no stop-and-go mid-way)
      if (t < 0.5) quat.slerpQuaternions(Q2, Q3, t * 2);
      else quat.slerpQuaternions(Q3, Q4, (t - 0.5) * 2);
    } else {
      const t = heroScroll.cameraProgress; // already eased by GSAP
      pos.lerpVectors(P1, P2, t);
      quat.slerpQuaternions(Q1, Q2, t);
    }

    const zooms = [
      heroScroll.comp1ZoomProgress,
      heroScroll.zoomProgress,
      heroScroll.comp3ZoomProgress,
      heroScroll.comp4ZoomProgress,
      heroScroll.comp5ZoomProgress,
    ];
    const active = zooms.findIndex((z) => z > 0.0001);
    if (active >= 0) {
      closeUp(cam, gl.domElement, active, tmp);
      const z = zooms[active];
      pos.lerp(tmp.close, z);
      quat.slerp(Q_CLOSE, z);
    }

    cam.position.copy(pos);
    cam.quaternion.copy(quat);
  });

  return null;
}

/** Camera position for a close-up of compartment `i`, so it lands on SCREEN_SPOT[i]. */
function closeUp(
  cam: THREE.PerspectiveCamera,
  canvas: HTMLCanvasElement,
  i: number,
  v: { fwd: THREE.Vector3; right: THREE.Vector3; up: THREE.Vector3; close: THREE.Vector3 },
) {
  const target = compartmentTargets[i];
  const tanHalf = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));

  // The canvas is much wider than the viewport and slides with the layout,
  // so map the desired viewport point into the canvas's own NDC.
  const rect = canvas.getBoundingClientRect();
  const [sx, sy] = SCREEN_SPOT[i];
  const nx = ((sx * window.innerWidth - rect.left) / rect.width) * 2 - 1;
  const ny = -(((sy * window.innerHeight - rect.top) / rect.height) * 2 - 1);

  // distance so the compartment fills FILL of the viewport height
  const visibleH = (target.size / FILL) * (rect.height / window.innerHeight);
  const dist = visibleH / (2 * tanHalf);

  v.fwd.set(0, 0, -1).applyQuaternion(Q_CLOSE);
  v.right.set(1, 0, 0).applyQuaternion(Q_CLOSE);
  v.up.set(0, 1, 0).applyQuaternion(Q_CLOSE);

  const dx = nx * dist * tanHalf * cam.aspect;
  const dy = ny * dist * tanHalf;
  v.close
    .copy(target.center)
    .addScaledVector(v.fwd, -dist)
    .addScaledVector(v.right, -dx)
    .addScaledVector(v.up, -dy);
}
