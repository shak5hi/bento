import { Header } from './components/common/Header';
import { Canvas } from '@react-three/fiber';
import { Environment } from '@react-three/drei';
import { BentoModel } from './experience/models/BentoModel';
import { Suspense } from 'react';
import { SmoothScroll } from './components/common/SmoothScroll';
import { HeroText } from './components/common/HeroText';

export default function App() {
  return (
    <SmoothScroll>
      <div className="w-full bg-bento-bg text-bento-text relative overflow-x-hidden">
        
        {/* Fixed 3D Background */}
        <div className="fixed top-0 left-0 w-full h-screen z-0 pointer-events-none">
          <Canvas shadows camera={{ position: [0, 2, 10], fov: 35 }} dpr={[1, 2]}>
            <Suspense fallback={null}>
              <ambientLight intensity={0.4} />
              <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow shadow-mapSize={1024} />
              <Environment preset="studio" />
              
              <BentoModel position={[0, -1, 0]} scale={1.3} />
            </Suspense>
          </Canvas>
        </div>

        {/* UI Overlay (Scrollable Container for GSAP to track) */}
        <div className="relative z-10 w-full h-[400vh]">
          <div className="absolute top-0 h-screen w-full">
             <Header />
             <HeroText />
          </div>
        </div>
      </div>
    </SmoothScroll>
  );
}
