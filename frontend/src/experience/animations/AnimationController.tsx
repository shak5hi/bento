import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

export function AnimationController() {
  const { camera } = useThree();

  useEffect(() => {
    // NO ANIMATION per instructions
    
    // Increased distance until ENTIRE Bento Box fits comfortably
    const distance = 16; 
    // Approximately 25-30 degree downward viewing angle
    const angle = 28 * (Math.PI / 180);
    
    camera.position.set(0, distance * Math.sin(angle), distance * Math.cos(angle));
    camera.fov = 30; // Kept lower fov for less distortion, or we could use 50. 30 is fine with larger distance.
    
    // Look at center of Bento Box
    const target = new THREE.Vector3(0, 0, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();

  }, [camera]);

  return null;
}
