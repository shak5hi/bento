import React from 'react';
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

  // ── Compute tray top surface Y so we can place lid flush on it ──────
  // We need to measure the tray AFTER the rotation is applied.
  // We'll clone the scene, apply the rotation to a temp group, measure it.
  const tempTray = trayScene.clone();
  const tempLid  = lidScene.clone();

  // Apply the same rotation we'll use in the scene
  const euler = new THREE.Euler(Math.PI, 0.4, 0);
  tempTray.setRotationFromEuler(euler);
  tempLid.setRotationFromEuler(euler);

  const trayBox = new THREE.Box3().setFromObject(tempTray);
  const lidBox  = new THREE.Box3().setFromObject(tempLid);

  // Top of tray and bottom of lid (in their rotated space)
  const trayTop   = trayBox.max.y;
  const lidBottom = lidBox.min.y;
  const lidYOffset = trayTop - lidBottom;

  return (
    <group position={position} scale={scale}>
      {/*
        rotation X = Math.PI → flip the tray right-side up (exterior up, not interior)
        rotation Y = 0.4     → slight 3/4 turn for perspective (matches reference)
        No Z tilt needed — camera angle handles the look
      */}
      <group rotation={[Math.PI, 0.4, 0]}>
        {/* Orange tray — exterior side facing up */}
        <primitive object={trayScene} />

        {/* Black lid — sits on top of tray via computed offset */}
        <group
          ref={lidRef}
          name="bento-lid"
          position={[0, lidYOffset, 0]}
        >
          <primitive object={lidScene} />
        </group>
      </group>
    </group>
  );
}

useGLTF.preload('/models/trey.glb');
useGLTF.preload('/models/lid.glb');
