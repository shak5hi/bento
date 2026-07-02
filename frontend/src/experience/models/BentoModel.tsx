import React, { useRef, useEffect } from 'react';
import { useGLTF } from '@react-three/drei';
import { lidRef } from '../refs/bentoRefs';
import * as THREE from 'three';

interface BentoModelProps {
  position?: [number, number, number];
  scale?: number;
}

export function BentoModel({ position = [0, 0, 0], scale = 1 }: BentoModelProps) {
  const { scene: trayScene } = useGLTF('/models/trey.glb');
  const { scene: lidScene } = useGLTF('/models/lid.glb');
  
  const outerRef = useRef<THREE.Group>(null);
  const trayRef = useRef<THREE.Group>(null);
  const aligned = useRef(false);

  useEffect(() => {
    if (aligned.current) return;
    const outer = outerRef.current;
    const tray = trayRef.current;
    const lid = lidRef.current;
    if (!outer || !tray || !lid) return;

    // Force world-matrix computation
    outer.updateWorldMatrix(true, true);

    const trayBox = new THREE.Box3().setFromObject(tray);
    const lidBox = new THREE.Box3().setFromObject(lid);

    // 1. Ground the tray: shift outer group so tray bottom is at Y=0
    const groundOffset = -trayBox.min.y;
    outer.position.y += groundOffset;

    // 2. Recompute after grounding
    outer.updateWorldMatrix(true, true);
    const trayBoxGrounded = new THREE.Box3().setFromObject(tray);
    const lidBoxGrounded = new THREE.Box3().setFromObject(lid);

    // 3. Place lid so its bottom sits on the tray top rim
    const lidOffset = trayBoxGrounded.max.y - lidBoxGrounded.min.y;
    lid.position.y += lidOffset;

    aligned.current = true;
  }, [trayScene, lidScene]);

  return (
    <group ref={outerRef} position={position} scale={scale}>
      {/* 
        Setting rotation to 0 so the box faces perfectly straight.
        The reference image shows it straight-on (parallel), not diagonal.
      */}
      <group rotation={[0, 0, 0]}>
        {/* Tray */}
        <group ref={trayRef}>
          <primitive object={trayScene} />
        </group>
        
        {/* Lid - Bring it back, flip it so the black exterior faces up, and place it perfectly on top */}
        <group ref={lidRef} name="bento-lid" rotation={[Math.PI, 0, 0]}>
          <primitive object={lidScene} />
        </group>
      </group>
    </group>
  );
}

useGLTF.preload('/models/trey.glb');
useGLTF.preload('/models/lid.glb');
