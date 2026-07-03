import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { SoftShadows, Environment } from '@react-three/drei';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import * as THREE from 'three';
import './HeroLayout.css';

function BentoHero() {
  return (
    <div className="hero-container">
      {/* DOM UI overlay - left column only */}
      <div className="hero-left-col">
        <div className="logo">BENT<span>🍱</span></div>
        <h1 className="heading">Everything<br />you're<br />building.</h1>
        <p className="paragraph">
          One beautiful place.<br />
          A workspace designed for clarity —<br />
          no clutter, just your best work.
        </p>
        <div className="cta-group">
          <button className="btn-primary">Get Started</button>
          <button className="btn-secondary">See how it works &rarr;</button>
        </div>
      </div>

      {/* R3F Canvas - Right column only */}
      <div className="hero-right-col">
        <Canvas 
          shadows 
          dpr={[1, 2]} 
          gl={{ 
            antialias: true,
            toneMapping: THREE.ACESFilmicToneMapping,
            outputColorSpace: THREE.SRGBColorSpace
          }} 
          className="hero-canvas"
        >
          <AnimationController />
          
          <Suspense fallback={null}>
            <SoftShadows size={15} samples={10} focus={0.5} />
            
            {/* Soft, realistic studio lighting */}
            <ambientLight intensity={0.55} />
            
            <directionalLight 
              position={[6, 8, 4]} 
              intensity={2.2} 
              castShadow 
              shadow-mapSize={[2048, 2048]} 
              shadow-bias={-0.0001} 
            />
            
            <directionalLight 
              position={[-5, 2, -4]} 
              intensity={0.35} 
            />
            
            <Environment preset="city" />
            
            <BentoModel />
          </Suspense>
        </Canvas>
      </div>
    </div>
  );
}

export default function App() {
  return <BentoHero />;
}
