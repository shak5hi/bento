import { useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, ContactShadows } from '@react-three/drei';
import { Header } from './components/common/Header';
import { HeroText } from './components/common/HeroText';
import { SmoothScroll } from './components/common/SmoothScroll';
import { BentoModel } from './experience/models/BentoModel';
import { useLidAnimation } from './experience/animations/useLidAnimation';

function BentoHero() {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  useLidAnimation(scrollContainerRef);

  return (
    <SmoothScroll>
      {/* Tall scrollable page — the lid animation plays over the first 300vh */}
      <div ref={scrollContainerRef} style={{ width: '100%', minHeight: '300vh', backgroundColor: '#F15A24', position: 'relative', overflowX: 'hidden' }}>

        {/* Fixed Canvas — right 40% only */}
        <div style={{ position: 'fixed', top: 0, right: 0, width: '40%', height: '100vh', zIndex: 0 }}>
          <Canvas
            shadows
            camera={{ position: [0, 5.5, 4.5], fov: 36 }}
            dpr={[1, 2]}
            gl={{ antialias: true }}
          >
            <Suspense fallback={null}>
              {/* Moderate key light from upper-left */}
              <directionalLight position={[-5, 8, 5]} intensity={1.5} castShadow />
              {/* Subtle fill from right bottom */}
              <directionalLight position={[4, 1, 3]} intensity={0.2} color="#ff8c55" />
              {/* Very low ambient */}
              <ambientLight intensity={0.06} />
              <Environment preset="studio" />
              <group position={[-0.8, -0.2, 0]}>
                <BentoModel position={[0, 0, 0]} scale={0.55} />
                <ContactShadows
                  position={[0, 0, 0]}
                  opacity={0.55}
                  scale={5}
                  blur={2.5}
                  far={2}
                  color="#000"
                />
              </group>
            </Suspense>
          </Canvas>
        </div>

        {/* Sticky overlay — header + left text panel */}
        <div style={{ position: 'sticky', top: 0, height: '100vh', width: '100%', zIndex: 10, pointerEvents: 'none' }}>
          
          {/* Header bar — full width, above everything */}
          <div style={{ pointerEvents: 'auto', position: 'absolute', top: 0, left: 0, width: '100%' }}>
            <Header />
          </div>

          {/* Left column text — 60% width */}
          <div style={{ display: 'flex', height: '100%', width: '100%' }}>
            <div style={{ width: '60%', height: '100%', pointerEvents: 'auto' }}>
              <HeroText />
            </div>
            {/* Right 40% transparent — canvas shows through */}
            <div style={{ width: '40%' }} />
          </div>

          {/* "Scroll to open" cue */}
          <div
            style={{
              position: 'absolute',
              bottom: '2.5rem',
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '0.5rem',
              opacity: 0.5,
              pointerEvents: 'none',
            }}
          >
            <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#1a1a1a' }}>
              Scroll to open
            </span>
            <svg width="12" height="18" viewBox="0 0 12 18" fill="none" className="animate-bounce">
              <path d="M6 0v16M1 11l5 5 5-5" stroke="#1a1a1a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>

      </div>
    </SmoothScroll>
  );
}

export default function App() {
  return <BentoHero />;
}
