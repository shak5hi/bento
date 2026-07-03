import { useEffect, useRef } from 'react';
import { useGLTF, useAnimations } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export function BentoModel() {
  const group = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF('/models/bento.glb');
  const { actions, mixer, names } = useAnimations(animations, group);
  
  // Use a ref to store the scrub time so useFrame can read it without dependencies
  const scrub = useRef({ time: 0 });

  useEffect(() => {
    scene.traverse((child) => {
      if ((child as THREE.Mesh).isMesh || (child as THREE.SkinnedMesh).isSkinnedMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        child.frustumCulled = false;
      }
    });
  }, [scene]);

  useEffect(() => {
    if (names.length === 0) return;
    const action = actions[names[0]];
    if (!action) return;

    action.play();
    action.paused = true; // Stop automatic time advancement
    
    // Force the mixer to evaluate frame 0 immediately so it doesn't vanish on mount
    mixer.setTime(0);
    
    const duration = action.getClip().duration;
    
    // Find a scrollable wrapper (if .hero-container is 100vh, the body must scroll)
    // We will just bind it to the hero container, scrubbing as it scrolls out of view.
    const scrollContainer = document.querySelector('.hero-container') || document.body;

    const ctx = gsap.context(() => {
      gsap.to(scrub.current, {
        time: duration,
        ease: 'none',
        scrollTrigger: {
          trigger: scrollContainer,
          start: 'top top',
          end: 'bottom top',
          scrub: 1.5
        }
      });
    });

    return () => ctx.revert();
  }, [actions, names, mixer]);

  useFrame(() => {
    if (names.length > 0 && actions[names[0]]) {
      // Continuously force the action to whatever time GSAP calculated
      actions[names[0]].time = scrub.current.time;
    }
  });

  return (
    <group ref={group} position={[2.3, -0.28, 0]} rotation={[0, -0.18, 0]} scale={0.82}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload('/models/bento.glb');
