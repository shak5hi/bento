import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

export function AnimationController() {
  const { camera } = useThree();

  useEffect(() => {
    // NO ANIMATION per instructions
    
    // Prompt: Camera initialization
    // Position: X=0, Y=3.8, Z=6.0
    // Rotation: X=-28deg, Y=0, Z=0
    // LookAt: X=0.65, Y=0, Z=0
    camera.position.set(0, 3.8, 6.0);
    camera.rotation.set(-28 * (Math.PI / 180), 0, 0);
    camera.fov = 30;
    
    // Overriding rotation with exact lookAt target per instructions
    const target = new THREE.Vector3(0.65, 0, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();

  }, [camera]);

  return null;
}
