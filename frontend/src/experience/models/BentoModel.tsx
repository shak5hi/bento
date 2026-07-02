import React, { useRef } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';

export function BentoModel(props: JSX.IntrinsicElements['group']) {
  const { scene } = useGLTF('/models/bentocomponents.glb');

  return (
    <group {...props} dispose={null}>
      {/* 
        Blender uses Z-up, Three.js uses Y-up. 
        If the model is lying on its side (lid not on top), we rotate it 90 degrees.
      */}
      <primitive object={scene} rotation={[Math.PI / 2, 0, 0]} />
    </group>
  );
}

useGLTF.preload('/models/bentocomponents.glb');
