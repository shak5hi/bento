import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import * as THREE from 'three';
import './HeroLayout.css';

function BentoHero() {
  return (
    /**
     * .hero-container is 200vh tall — this gives GSAP ScrollTrigger room to
     * scrub the lid animation as the user scrolls. The visual content is
     * sticky inside .hero-content (always 100vh tall).
     */
    <div className="hero-container">
      <div className="hero-content">

        {/* ── Left column ────────────────────────────────── */}
        <div className="hero-left-col">
          <div className="logo">
            BENT<span>🍱</span>
          </div>

          <h1 className="heading">
            Every project deserves<br />
            a place at<br />
            the table.
          </h1>

          <p className="paragraph">
            One beautiful place.<br />
            A workspace designed for clarity —<br />
            no clutter, just your best work.
          </p>

          <div className="cta-group">
            <button className="btn-primary">Get Started</button>
            <button className="btn-secondary">See how it works →</button>
          </div>
        </div>

        {/* ── Right column — 3D Canvas ────────────────────── */}
        <div className="hero-right-col">
          <Canvas
            shadows
            /**
             * Camera initial values match the approved debug session framing.
             * AnimationController sets lookAt immediately after mount.
             */
            camera={{ position: [-26.011, 13.694, 5.510], fov: 20 }}
            dpr={[1, 2]}
            gl={{
              antialias: true,
              toneMapping: THREE.ACESFilmicToneMapping,
              outputColorSpace: THREE.SRGBColorSpace,
            }}
            className="hero-canvas"
          >
            {/* Locks the camera to the approved framing — no OrbitControls */}
            <AnimationController />

            <Suspense fallback={null}>
              {/* Reduced lighting — enough for 3D depth, not enough to wash out color */}
              <ambientLight intensity={1.8} />
              <directionalLight position={[-8, 10, 5]} intensity={3.6} color="#fff5ee" />
              <directionalLight position={[5, 4, -4]} intensity={1.1} color="#ffffff" />

              {/* Bento Box — lid frozen at frame 0 */}
              <BentoModel />
            </Suspense>
          </Canvas>
        </div>
      </div>{/* end .hero-content */}

      {/* Scroll hint — outside the grid so it doesn't become a 3rd grid child */}
      <div className="scroll-hint">Scroll to open</div>
    </div>
  );
}

export default function App() {
  return <BentoHero />;
}
