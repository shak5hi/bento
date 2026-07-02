import { Header } from './components/common/Header';
import { Canvas } from '@react-three/fiber';
import { Environment, PresentationControls, Float } from '@react-three/drei';
import { BentoModel } from './experience/models/BentoModel';
import { Suspense } from 'react';

export default function App() {
  return (
    <div className="w-full h-screen bg-bento-bg text-bento-text flex flex-col relative overflow-hidden">
      <Header />
      
      <main className="flex-1 flex flex-col md:flex-row relative z-10">
        
        {/* Left Side: Typography */}
        <div className="flex-1 flex flex-col justify-center px-12 md:px-24 lg:pl-32 pb-12 pt-32 md:pt-0 z-20 pointer-events-none">
          <div className="max-w-2xl w-full flex flex-col items-start pointer-events-auto">
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-semibold tracking-tighter text-bento-text leading-[1.05]">
              Everything you're building.<br/>
              One beautiful place.
            </h1>
            <p className="mt-8 text-lg md:text-xl text-bento-text font-medium opacity-70 max-w-xl leading-relaxed">
              A workspace designed for clarity. No clutter, just your best work.
            </p>
            <button className="mt-10 px-8 py-3 bg-bento-lid text-bento-cream rounded-full font-medium text-sm hover:scale-[0.98] transition-transform duration-300 shadow-xl">
              Get Started
            </button>
          </div>
        </div>

        {/* Right Side: 3D Canvas */}
        <div className="flex-1 h-full w-full relative z-10 cursor-grab active:cursor-grabbing">
          <Canvas shadows camera={{ position: [0, 2, 10], fov: 35 }} dpr={[1, 2]}>
            <Suspense fallback={null}>
              {/* Soft studio lighting */}
              <ambientLight intensity={0.4} />
              <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow shadow-mapSize={1024} />
              <Environment preset="studio" />
              
              <PresentationControls 
                global 
                rotation={[0, 0, 0]} 
                polar={[-0.4, 0.2]} 
                azimuth={[-0.5, 0.5]} 
                config={{ mass: 2, tension: 400 }} 
                snap={{ mass: 4, tension: 400 }}
              >
                <Float rotationIntensity={0.1} floatIntensity={0.2} speed={2}>
                  <BentoModel position={[0, -0.5, 0]} scale={1.2} />
                </Float>
              </PresentationControls>
            </Suspense>
          </Canvas>
        </div>

      </main>
    </div>
  );
}
