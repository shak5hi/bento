import { useEffect, useRef, useMemo } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { heroScroll } from '../scrollState';

/**
 * AnimationController — animates the camera to the centered framing.
 */
export function AnimationController() {
  const { camera } = useThree();

  // Initial and Final camera positions
  const startPos = useMemo(() => new THREE.Vector3(-26.011, 13.694, 5.510), []);
  const endPos = useMemo(() => new THREE.Vector3(6.109, 21.582, 8.014), []);
  
  // The camera pulls back to this position while the box opens to fit the lid
  const openPos = useMemo(() => new THREE.Vector3(12.229, 20.986, 8.238), []);
  
  // Target stays exactly the same
  const target = useMemo(() => new THREE.Vector3(0.0, 1.209, 0.0), []);

  useFrame(() => {
    const cam = camera as THREE.PerspectiveCamera;
    
    if (heroScroll.rawProgress > 0) {
      // 50% -> 100%: Box is opening. Lerp from endPos to openPos
      const easeProgress = 1 - Math.pow(1 - heroScroll.rawProgress, 3);
      cam.position.lerpVectors(endPos, openPos, easeProgress);
    } else {
      // 0% -> 50%: Box is closed. Lerp from startPos to endPos
      cam.position.lerpVectors(startPos, endPos, heroScroll.cameraProgress);
    }
    
    // Always look at the target
    cam.lookAt(target);
  });

  return null;
}
