import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Environment, Lightformer } from '@react-three/drei';
import * as THREE from 'three';
import { BentoModel } from './models/BentoModel';

// Slowly turns the box so the half-open lid catches the light.
function Turntable({ children }: { children: React.ReactNode }) {
  const ref = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.rotation.y = Math.sin(clock.elapsedTime * 0.25) * 0.18;
  });
  return <group ref={ref}>{children}</group>;
}

/** The landing page's lacquer bento, lid half open, for the login page's art panel. */
export default function LoginBento() {
  return (
    <Canvas
      shadows
      camera={{ position: [-15, 13, 15], fov: 24 }}
      onCreated={({ camera }) => camera.lookAt(0.4, 1.1, 0)}
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping, outputColorSpace: THREE.SRGBColorSpace }}
      className="auth-canvas"
    >
      <ambientLight intensity={0.5} />
      <directionalLight castShadow position={[-7, 16, 9]} intensity={2.4} color="#fff4e8" shadow-mapSize={[1024, 1024]} shadow-bias={-0.0003} shadow-normalBias={0.02} />
      <directionalLight position={[9, 5, -7]} intensity={0.8} color="#ffcfb0" />
      <Environment resolution={128} frames={1}>
        <Lightformer form="rect" intensity={1.6} position={[-5, 9, 3]} rotation-x={Math.PI / 2} rotation-z={0.6} scale={[2.2, 16, 1]} />
        <Lightformer form="rect" intensity={0.9} color="#ffe6d2" position={[-8, 4, 6]} rotation-y={Math.PI / 3} scale={[8, 3, 1]} />
      </Environment>
      <Suspense fallback={null}>
        <Turntable>
          <BentoModel ajar />
        </Turntable>
      </Suspense>
    </Canvas>
  );
}
