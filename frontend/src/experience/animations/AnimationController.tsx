import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * AnimationController — locks the camera to the approved product framing.
 * Position and target approved by the user via OrbitControls debug session.
 * DO NOT modify these values.
 */
export function AnimationController() {
  const { camera } = useThree();

  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;

    // Approved camera position — do not change
    cam.position.set(-26.011, 13.694, 5.510);

    // Approved FOV
    cam.fov = 20;

    // Aim at approved target
    cam.lookAt(new THREE.Vector3(0.0, 1.209, 0.0));

    cam.updateProjectionMatrix();
  }, [camera]);

  return null;
}
