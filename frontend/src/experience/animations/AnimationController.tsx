import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

export function AnimationController() {
  const { camera } = useThree();

  useEffect(() => {
    // Apple-style framing: Pulled back, fov 26, looking slightly downward
    camera.position.set(0.8, 1.0, 6.2);
    (camera as THREE.PerspectiveCamera).fov = 26;
    
    const target = new THREE.Vector3(2.2, 0.2, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();

  }, [camera]);

  return null;
}
