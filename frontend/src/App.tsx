import { useEffect, useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import * as THREE from 'three';
import logoSrc from './assets/logo.png';
import './HeroLayout.css';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { heroScroll } from './experience/scrollState';

gsap.registerPlugin(ScrollTrigger);

function BentoHero() {
  const containerRef = useRef<HTMLDivElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const rightColRef = useRef<HTMLDivElement>(null);
  const scrollHintRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !leftColRef.current || !rightColRef.current) return;

    // Use gsap.context to manage cleanup
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: 'bottom bottom',
          scrub: 2.5, // Much higher scrub value for buttery smooth, heavy Apple-style movement
          invalidateOnRefresh: true, // Recalculate function-based values on resize
        }
      });

      // 1. Map timeline to exactly 100 duration to match 0-100% scroll progress
      tl.to({}, { duration: 100 });

      // 2. SECTION 2A — TEXT EXITS (10% -> 20%)
      tl.to([leftColRef.current, scrollHintRef.current], {
        xPercent: -80,
        opacity: 0,
        ease: 'power2.inOut',
        duration: 10
      }, 10);

      // 2. SECTION 2B — CAMERA MOVES & BOX CENTERS (20% -> 48%) - Slow and smooth
      const camProxy = { progress: 0 };
      tl.to(camProxy, {
        progress: 1,
        ease: 'power3.inOut',
        duration: 28,
        onUpdate: () => {
          heroScroll.cameraProgress = camProxy.progress;
        }
      }, 20);

      // Simultaneously physically move the container to the center of the screen
      tl.to(rightColRef.current, {
        x: () => {
          const parent = rightColRef.current!.parentElement;
          if (!parent) return 0;
          const style = window.getComputedStyle(parent);
          const paddingLeft = parseFloat(style.paddingLeft) || 0;
          const paddingRight = parseFloat(style.paddingRight) || 0;
          const contentWidth = parent.getBoundingClientRect().width - paddingLeft - paddingRight;
          return -0.26 * contentWidth;
        },
        ease: 'power3.inOut',
        duration: 28
      }, 20);

      // 3. SECTION 3 — PAUSE (48% -> 50%)
      // Nothing is scheduled here, the timeline naturally pauses

      // 4. SECTION 4 — OPENING (50% -> 100%)
      const proxy = { progress: 0 };
      tl.to(proxy, {
        progress: 1,
        ease: 'none',
        duration: 50,
        onUpdate: () => {
          heroScroll.rawProgress = proxy.progress;
        }
      }, 50);
    });

    return () => ctx.revert();
  }, []);

  return (
    /**
     * .hero-container height gives GSAP ScrollTrigger room to scrub.
     * The visual content is sticky inside .hero-content.
     */
    <div className="hero-container" ref={containerRef}>
      <div className="hero-content">

        {/* ── Left column ────────────────────────────────── */}
        <div className="hero-left-col" ref={leftColRef}>
          <div className="logo">
            <img src={logoSrc} alt="Bento" className="logo-img" />
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
        <div className="hero-right-col" ref={rightColRef}>
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
      <div className="scroll-hint" ref={scrollHintRef}>Scroll to open</div>
    </div>
  );
}

export default function App() {
  return <BentoHero />;
}
