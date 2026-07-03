import { useEffect, useMemo, useRef } from 'react';
import { useGLTF, useAnimations } from '@react-three/drei';
import { useFrame, createPortal } from '@react-three/fiber';
import * as THREE from 'three';
import { heroScroll } from '../scrollState';
import { FoodItems } from './FoodItems';


/**
 * BentoModel — loads bento.glb and scrubs the Blender lid animation via scroll.
 *
 * Rules:
 * - Do NOT modify geometry, materials, or GLB hierarchy.
 * - Scale is always uniform (scalar, not array).
 * - Animation scale tracks stripped to prevent non-uniform deformation.
 * - Lid starts closed at frame 0. Animation plays only as the user scrolls.
 */
export function BentoModel() {
  const group = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF('/models/bento.glb');

  // Memoised: strip scale tracks so the animation can never non-uniformly deform the model.
  // Without useMemo this runs every render, causing useAnimations to re-bind on every frame.
  const cleanedAnimations = useMemo(
    () =>
      animations.map((clip) => {
        const clone = clip.clone();
        clone.tracks = clone.tracks.filter((t) => !t.name.endsWith('.scale'));
        return clone;
      }),
    [animations]
  );

  const { actions, mixer, names } = useAnimations(cleanedAnimations, group);

  // We no longer need local ref for scrub, we read heroScroll directly in useFrame.
  // Use MeshStandardMaterial so lighting gives proper 3D depth.
  // Colors: tray = #762C0B (deep terracotta), lid = #2d2d2d (charcoal).
  useEffect(() => {
    const TRAY_MAT = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#762C0B'),
      roughness: 0.65,
      metalness: 0.05,
    });
    const LID_MAT = new THREE.MeshStandardMaterial({
      color: new THREE.Color('#2d2d2d'),
      roughness: 0.45,
      metalness: 0.05,
    });

    scene.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) return;

      // Protect the food items from being painted with the tray material
      if (mesh.name.toLowerCase().includes('food')) return;

      const isLid = mesh.name.toLowerCase().includes('lid') ||
                    child.parent?.name.toLowerCase().includes('lid');

      mesh.material = isLid ? LID_MAT : TRAY_MAT;
      mesh.frustumCulled = false;
    });
  }, [scene]);

  // Connect Blender animation to our scroll state (0 -> 1 progress maps to 0 -> clip.duration)
  useEffect(() => {
    if (!names.length) return;
    const action = actions[names[0]];
    if (!action) return;

    action.play();
    action.paused = true;
    mixer.setTime(0);
  }, [actions, names, mixer]);

  // Every frame: apply the shared scroll progress to the action time
  useFrame(() => {
    const action = names.length ? actions[names[0]] : null;
    if (action) {
      action.time = heroScroll.rawProgress * action.getClip().duration;
    }
  });
  const treyNode = useMemo(() => {
    let found = null;
    scene.traverse((child) => {
      if (child.name.toLowerCase().includes('trey') || child.name.toLowerCase().includes('tray')) {
        found = child;
      }
    });
    return found || scene;
  }, [scene]);

  return (
    <group ref={group} position={[0, 0.8, 0]} rotation={[0, Math.PI / 6, 0]} scale={1.8}>
      <primitive object={scene} />
      {treyNode && createPortal(<FoodItems />, treyNode)}
    </group>
  );
}

useGLTF.preload('/models/bento.glb');
