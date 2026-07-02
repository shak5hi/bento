import React from 'react';
import { useGLTF } from '@react-three/drei';

export function BentoModel(props: JSX.IntrinsicElements['group']) {
  const { scene: trayScene } = useGLTF('/models/trey.glb');
  const { scene: lidScene } = useGLTF('/models/lid.glb');

  return (
    <group {...props} dispose={null}>
      <group rotation={[Math.PI / 2, 0, 0]}>
        {/* Tray */}
        <primitive object={trayScene} />
        
        {/* Lid (Needs to be in its own group with a ref for GSAP animation later) */}
        <group name="bento-lid">
          <primitive object={lidScene} />
        </group>
      </group>
    </group>
  );
}

useGLTF.preload('/models/trey.glb');
useGLTF.preload('/models/lid.glb');
