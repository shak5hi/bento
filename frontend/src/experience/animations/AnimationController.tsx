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
  const p5 = useMemo(() => new THREE.Vector3(2.4, 2.5, 0.75), []);
  const e5 = useMemo(() => new THREE.Euler(-1.496, 0.042, 0.505), []);
  const q5 = useMemo(() => new THREE.Quaternion().setFromEuler(e5), [e5]);

  useFrame(() => {
    const cam = camera as THREE.PerspectiveCamera;
    
    if (heroScroll.zoomProgress > 0) {
      // 110% -> 140% of page scroll (Zooming into Compartment 2)
      const ease = heroScroll.zoomProgress; // GSAP handles the easing
      cam.position.lerpVectors(p4, p5, ease);
      cam.quaternion.slerpQuaternions(q4, q5, ease);
    } else if (heroScroll.rawProgress > 0) {
      // 50% -> 100% of page scroll (Box is opening)
      const p = heroScroll.rawProgress; // 0 to 1
      
      if (p <= 0.5) {
        // First half of opening: Keyframe 2 -> Keyframe 3
        const localP = p * 2; // 0 to 1
        const ease = 1 - Math.pow(1 - localP, 3); // cubic out for smoothness
        cam.position.lerpVectors(p2, p3, ease);
        cam.quaternion.slerpQuaternions(q2, q3, ease);
      } else {
        // Second half of opening: Keyframe 3 -> Keyframe 4
        const localP = (p - 0.5) * 2; // 0 to 1
        const ease = 1 - Math.pow(1 - localP, 3); // cubic out for smoothness
        cam.position.lerpVectors(p3, p4, ease);
        cam.quaternion.slerpQuaternions(q3, q4, ease);
      }
    } else {
      // 0% -> 50% of page scroll (Box is closed, camera is centering)
      // Transition: Keyframe 1 -> Keyframe 2
      const ease = heroScroll.cameraProgress; // already smoothed by GSAP power3.inOut
      cam.position.lerpVectors(p1, p2, ease);
      cam.quaternion.slerpQuaternions(q1, q2, ease);
    }
  });

  return null;
}
