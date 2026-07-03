import { useMemo } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { heroScroll } from '../scrollState';

/**
 * AnimationController — animates the camera to the centered framing.
 */
export function AnimationController() {
  const { camera } = useThree();

  // --- Keyframe 1 (Start) ---
  const p1 = useMemo(() => new THREE.Vector3(19.275, 25.827, 13.350), []);
  const e1 = useMemo(() => new THREE.Euler(-1.094, 0.585, 0.819), []);
  const q1 = useMemo(() => new THREE.Quaternion().setFromEuler(e1), [e1]);

  // --- Keyframe 2 (Centered) ---
  const p2 = useMemo(() => new THREE.Vector3(1.025, 34.861, 0.688), []);
  const e2 = useMemo(() => new THREE.Euler(-1.551, 0.029, 0.979), []);
  const q2 = useMemo(() => new THREE.Quaternion().setFromEuler(e2), [e2]);

  // --- Keyframe 3 (Opening - Midpoint) ---
  const p3 = useMemo(() => new THREE.Vector3(1.901, 34.709, 2.912), []);
  const e3 = useMemo(() => new THREE.Euler(-1.487, 0.055, 0.576), []);
  const q3 = useMemo(() => new THREE.Quaternion().setFromEuler(e3), [e3]);

  // --- Keyframe 4 (End) ---
  const p4 = useMemo(() => new THREE.Vector3(0.745, 17.841, 1.343), []);
  const e4 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q4 = useMemo(() => new THREE.Quaternion().setFromEuler(e4), [e4]);

  // --- Keyframe 5 (Deep Zoom into Compartment 2 - Sushi) ---
  // Shifted more towards right
  const p5 = useMemo(() => new THREE.Vector3(2.2, 2.14, 1.0), []);
  const e5 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q5 = useMemo(() => new THREE.Quaternion().setFromEuler(e5), [e5]);

  // --- Keyframe 6 (Deep Zoom into Compartment 4) ---
  // Shifted more towards left
  const p6 = useMemo(() => new THREE.Vector3(-2.2, 1.78, -0.61), []);
  const e6 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q6 = useMemo(() => new THREE.Quaternion().setFromEuler(e6), [e6]);

  // --- Keyframe 7 (Deep Zoom into Compartment 1) ---
  const p7 = useMemo(() => new THREE.Vector3(0.5, 2.14, 1.6), []);
  const e7 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q7 = useMemo(() => new THREE.Quaternion().setFromEuler(e7), [e7]);

  // --- Keyframe 8 (Deep Zoom into Compartment 3) ---
  const p8 = useMemo(() => new THREE.Vector3(-1.5, 2.14, -1.2), []);
  const e8 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q8 = useMemo(() => new THREE.Quaternion().setFromEuler(e8), [e8]);

  // --- Keyframe 9 (Deep Zoom into Compartment 5) ---
  const p9 = useMemo(() => new THREE.Vector3(5.5, 2.14, -0.58), []);
  const e9 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q9 = useMemo(() => new THREE.Quaternion().setFromEuler(e9), [e9]);

  useFrame(() => {
    const cam = camera as THREE.PerspectiveCamera;
    
    // We will calculate a base position and then interpolate towards zoom targets
    let basePos = new THREE.Vector3();
    let baseQuat = new THREE.Quaternion();

    if (heroScroll.rawProgress > 0) {
      // 50% -> 100% of page scroll (Box is opening)
      const p = heroScroll.rawProgress; // 0 to 1
      
      if (p <= 0.5) {
        // First half of opening: Keyframe 2 -> Keyframe 3
        const localP = p * 2; // 0 to 1
        const ease = 1 - Math.pow(1 - localP, 3); // cubic out for smoothness
        basePos.lerpVectors(p2, p3, ease);
        baseQuat.slerpQuaternions(q2, q3, ease);
      } else {
        // Second half of opening: Keyframe 3 -> Keyframe 4
        const localP = (p - 0.5) * 2; // 0 to 1
        const ease = 1 - Math.pow(1 - localP, 3); // cubic out for smoothness
        basePos.lerpVectors(p3, p4, ease);
        baseQuat.slerpQuaternions(q3, q4, ease);
      }
    } else {
      // 0% -> 50% of page scroll (Box is closed, camera is centering)
      // Transition: Keyframe 1 -> Keyframe 2
      const ease = heroScroll.cameraProgress; // already smoothed by GSAP power3.inOut
      basePos.lerpVectors(p1, p2, ease);
      baseQuat.slerpQuaternions(q1, q2, ease);
    }

    // Now apply zoom overrides based on progress
    if (heroScroll.comp1ZoomProgress > 0) {
      basePos.lerp(p7, heroScroll.comp1ZoomProgress);
      baseQuat.slerp(q7, heroScroll.comp1ZoomProgress);
    }
    if (heroScroll.zoomProgress > 0) { // Comp 2
      basePos.lerp(p5, heroScroll.zoomProgress);
      baseQuat.slerp(q5, heroScroll.zoomProgress);
    }
    if (heroScroll.comp3ZoomProgress > 0) {
      basePos.lerp(p8, heroScroll.comp3ZoomProgress);
      baseQuat.slerp(q8, heroScroll.comp3ZoomProgress);
    }
    if (heroScroll.comp4ZoomProgress > 0) {
      basePos.lerp(p6, heroScroll.comp4ZoomProgress);
      baseQuat.slerp(q6, heroScroll.comp4ZoomProgress);
    }
    if (heroScroll.comp5ZoomProgress > 0) {
      basePos.lerp(p9, heroScroll.comp5ZoomProgress);
      baseQuat.slerp(q9, heroScroll.comp5ZoomProgress);
    }

    cam.position.copy(basePos);
    cam.quaternion.copy(baseQuat);
  });

  return null;
}
