import { useEffect, useMemo, useRef } from 'react';
import { useGLTF, useAnimations } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

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

  // GSAP writes scroll progress here; useFrame reads it every tick
  const scrub = useRef({ time: 0 });

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

      const isLid = mesh.name.toLowerCase().includes('lid') ||
                    child.parent?.name.toLowerCase().includes('lid');

      mesh.material = isLid ? LID_MAT : TRAY_MAT;
      mesh.frustumCulled = false;
    });
  }, [scene]);

  // Lid stays fully closed — animation disabled for now
  useEffect(() => {
    if (!names.length) return;
    const action = actions[names[0]];
    if (!action) return;

    action.play();
    action.paused = true;
    mixer.setTime(0);
    scrub.current.time = 0;
  }, [actions, names, mixer]);

  // Every frame: apply the GSAP-driven time to the action
  useFrame(() => {
    const action = names.length ? actions[names[0]] : null;
    if (action) action.time = scrub.current.time;
  });

  return (
    <group ref={group} position={[0, 0.8, 0]} rotation={[0, Math.PI / 6, 0]} scale={1.8}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload('/models/bento.glb');
