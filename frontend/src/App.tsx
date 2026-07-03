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
            <ambientLight intensity={0.5} />
            <rectAreaLight
              width={10}
              height={10}
              color="#ffffff"
              intensity={4}
              position={[5, 8, 5]}
              rotation={[-Math.PI / 3, Math.PI / 8, 0]}
            />
            {/* Directional light to cast shadows (since AreaLight doesn't) */}
            <directionalLight 
              position={[5, 8, 5]} 
              intensity={1.5} 
              castShadow 
              shadow-mapSize={[2048, 2048]} 
              shadow-bias={-0.0001} 
            />
            {/* Soft fill light */}
            <directionalLight position={[-4, 4, 2]} intensity={0.5} />
            
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
