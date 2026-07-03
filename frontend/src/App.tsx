import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { SoftShadows } from '@react-three/drei';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
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
        <Canvas shadows dpr={[1, 2]} gl={{ antialias: true }} className="hero-canvas">
          <AnimationController />
          
          <Suspense fallback={null}>
            <SoftShadows size={15} samples={10} focus={0.5} />
            
            {/* Lighting exactly as specified */}
            <pointLight position={[-2, 5, 3]} intensity={180} castShadow shadow-bias={-0.001} />
            <pointLight position={[4, 2, 4]} intensity={40} />
            <ambientLight intensity={0.45} />
            
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
