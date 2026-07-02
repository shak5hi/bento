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

        {/* Fixed Canvas — right half only */}
        <div style={{ position: 'fixed', top: 0, right: 0, width: '50%', height: '100vh', zIndex: 0 }}>
          <Canvas
            shadows
            camera={{ position: [0, 3.5, 8], fov: 36 }}
            dpr={[1, 2]}
            gl={{ antialias: true }}
          >
            <Suspense fallback={null}>
              {/* Strong key light from upper-left — gives the lid its signature dark sheen */}
              <directionalLight position={[-3, 6, 5]} intensity={2.5} castShadow />
              {/* Subtle warm fill from right */}
              <directionalLight position={[4, 2, 2]} intensity={0.4} color="#ffe4cc" />
              {/* Low ambient so shadows stay visible */}
              <ambientLight intensity={0.25} />
              <Environment preset="studio" />
              <BentoModel position={[0, -1, 0]} scale={1.6} />
              <ContactShadows
                position={[0, -2.2, 0]}
                opacity={0.35}
                scale={8}
                blur={2}
                far={4}
                color="#000"
              />
            </Suspense>
          </Canvas>
        </div>

        {/* Sticky overlay — header + left text panel */}
        <div style={{ position: 'sticky', top: 0, height: '100vh', width: '100%', zIndex: 10, pointerEvents: 'none' }}>
          
          {/* Header bar — full width, above everything */}
          <div style={{ pointerEvents: 'auto', position: 'absolute', top: 0, left: 0, width: '100%' }}>
            <Header />
          </div>

          {/* Left column text */}
          <div style={{ display: 'flex', height: '100%', width: '100%' }}>
            <div style={{ width: '50%', height: '100%', pointerEvents: 'auto' }}>
              <HeroText />
            </div>
            {/* Right half transparent — canvas shows through */}
            <div style={{ width: '50%' }} />
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
