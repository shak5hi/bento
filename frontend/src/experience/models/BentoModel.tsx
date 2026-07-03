import React, { useEffect, useMemo } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { lidRef } from '../refs/bentoRefs';

export function BentoModel() {
  const { scene: trayScene } = useGLTF('/models/trey.glb');
  const { scene: lidScene } = useGLTF('/models/lid.glb');

  // Compute bounding boxes to center models properly
  useMemo(() => {
    // Tray centering
    const tBox = new THREE.Box3().setFromObject(trayScene);
    const tCenter = tBox.getCenter(new THREE.Vector3());
    const tSize = tBox.getSize(new THREE.Vector3());

    // Center Tray X/Z
    trayScene.position.x = -tCenter.x;
    trayScene.position.z = -tCenter.z;
    // Place Tray bottom at Y=0
    trayScene.position.y = -tBox.min.y;

    // Lid centering
    const lBox = new THREE.Box3().setFromObject(lidScene);
    const lCenter = lBox.getCenter(new THREE.Vector3());

    // Center Lid X/Z
    lidScene.position.x = -lCenter.x;
    lidScene.position.z = -lCenter.z;
    // Sit perfectly on top of the tray (Tray top is at tSize.y since bottom is at 0)
    lidScene.position.y = -lBox.min.y + tSize.y;

  }, [trayScene, lidScene]);

  useEffect(() => {
    // Apply specified materials
    trayScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const material = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        material.color = new THREE.Color('#8B1C1C'); // Dark lacquer red
        material.roughness = 0.25; // Gentle glossy highlights
        material.metalness = 0.1;
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    lidScene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const material = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        material.color = new THREE.Color('#222222'); // Matte charcoal black
        material.roughness = 0.85; // Matte
        material.metalness = 0;
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });
  }, [trayScene, lidScene]);

  // Tiny Y rotation if necessary, but keep it almost straight
  const rotY = -2 * (Math.PI / 180);

  return (
    <group rotation={[0, rotY, 0]}>
      {/* Tray */}
      <group>
        <primitive object={trayScene} />
      </group>

      {/* Lid (Animated via lidRef but animations are disabled) */}
      <group ref={lidRef}>
        <primitive object={lidScene} />
      </group>
    </group>
  );
}

useGLTF.preload('/models/trey.glb');
useGLTF.preload('/models/lid.glb');
