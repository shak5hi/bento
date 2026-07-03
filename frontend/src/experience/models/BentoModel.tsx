import React, { useEffect } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { lidRef } from '../refs/bentoRefs';

export function BentoModel() {
  const { scene: trayScene } = useGLTF('/models/trey.glb');
  const { scene: lidScene } = useGLTF('/models/lid.glb');

  useEffect(() => {
    // Apply specified materials
    trayScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const material = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        material.color = new THREE.Color('#8B1C1C'); // Dark lacquer red
        material.roughness = 0.42;
        material.metalness = 0.05;
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    lidScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const material = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        material.color = new THREE.Color('#222222'); // Matte charcoal black
        material.roughness = 0.72;
        material.metalness = 0;
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
  }, [trayScene, lidScene]);

  // Prompt: Rotation Y = -8 degrees
  const rotY = -8 * (Math.PI / 180);

  return (
    <group>
      {/* Tray (Fixed) */}
      {/* Prompt: Position X=0.65, Y=-0.18, Z=0 */}
      <group position={[0.65, -0.18, 0]} rotation={[0, rotY, 0]}>
        <primitive object={trayScene} />
      </group>

      {/* Lid (Animated via lidRef) */}
      {/* Prompt: Position X=0.65, Y=0.06, Z=0 */}
      <group ref={lidRef} position={[0.65, 0.06, 0]} rotation={[0, rotY, 0]}>
        <primitive object={lidScene} />
      </group>
    </group>
  );
}

useGLTF.preload('/models/trey.glb');
useGLTF.preload('/models/lid.glb');
