import { useEffect, useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import * as THREE from 'three';
import logoSrc from './assets/logo.png';
import zoom2Img from './assets/compartmentzoom2.svg';
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
  const overlayRef = useRef<HTMLDivElement>(null);
  const zoom2Ref = useRef<HTMLImageElement>(null);
  const zoomTextRef = useRef<HTMLDivElement>(null);

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

      // 1. Map timeline to exactly 200 duration to make room for zoom out
      tl.to({}, { duration: 200 });

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

      // 5. SECTION 5 — PAUSE TO ADMIRE BOX (100% -> 110%)
      
      // 6. SECTION 6 — ZOOM INTO COMPARTMENT 2 (110% -> 140%)
      const zoomState = { progress: 0 };
      tl.to(zoomState, {
        progress: 1,
        ease: 'power3.inOut',
        duration: 30,
        onUpdate: () => {
          heroScroll.zoomProgress = zoomState.progress;
        }
      }, 110);

      // 7. SECTION 7 — FADE TO BENTO TRAY COLOR (135% -> 137%)
      tl.to(overlayRef.current, {
        opacity: 1,
        ease: 'power4.in',
        duration: 2
      }, 135);

      // 8. SECTION 8 — SUSHI IMAGE & TEXT SLIDE IN (137% -> 150%)
      tl.to([zoom2Ref.current, zoomTextRef.current], {
        opacity: 1,
        y: 0,
        ease: 'power3.out',
        duration: 13
      }, 137);

      // 9. SECTION 9 — ZOOM OUT AND RESET (170% -> 200%)
      // Hide UI
      tl.to([zoom2Ref.current, zoomTextRef.current], {
        opacity: 0,
        y: 50,
        ease: 'power3.in',
        duration: 10
      }, 170);

      // Hide background overlay
      tl.to(overlayRef.current, {
        opacity: 0,
        ease: 'power3.inOut',
        duration: 15
      }, 170);

      // Reverse camera zoom to go back to Keyframe 4
      tl.to(zoomState, {
        progress: 0,
        ease: 'power3.inOut',
        duration: 30,
        onUpdate: () => {
          heroScroll.zoomProgress = zoomState.progress;
        }
      }, 170);
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
            {/* The animation controller locks and moves the camera along the scroll path */}
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
      
      {/* Full screen fade overlay for entering the bento box */}
      <div 
        ref={overlayRef} 
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          backgroundColor: '#A13920', // Custom Bento tray terracotta color
          opacity: 0,
          pointerEvents: 'none',
          zIndex: 0
        }}
      />
      
      {/* Zoom 2 Image Overlay (Sushi Detail) */}
      <img
        src={zoom2Img}
        ref={zoom2Ref}
        alt="Sushi Detail"
        style={{
          position: 'fixed',
          top: '2vh',
          right: '-18vw',
          width: '65vw',
          opacity: 0,
          transform: 'translateY(100px)',
          zIndex: 10, // Above the background, but can be under text if needed
          pointerEvents: 'none'
        }}
      />

      {/* Zoom 2 Text Overlay */}
      <div
        ref={zoomTextRef}
        style={{
          position: 'fixed',
          top: '12vh',
          left: '4vw',
          width: '50vw',
          opacity: 0,
          transform: 'translateY(50px)',
          zIndex: 10,
          pointerEvents: 'none',
          color: '#fff',
          fontFamily: '"Arial Black", Impact, system-ui, -apple-system, sans-serif'
        }}
      >
        <h2 style={{
          fontSize: 'clamp(3.5rem, 5.5vw, 6.5rem)',
          fontWeight: 900,
          lineHeight: 0.85,
          letterSpacing: '-0.04em',
          textTransform: 'uppercase',
          margin: 0,
          marginBottom: '1.5rem',
          color: '#fff',
          whiteSpace: 'nowrap'
        }}>
          EVERY<br/>PROJECT<br/>STARTS<br/>WITH ONE PIECE.
        </h2>
        <p style={{
          fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
          fontSize: '1.25rem',
          lineHeight: 1.5,
          fontWeight: 400,
          color: 'rgba(255, 255, 255, 0.9)',
          maxWidth: '35ch',
          letterSpacing: '0.01em',
          whiteSpace: 'normal'
        }}>
          Create, improve, and watch your ideas come together into something complete.
        </p>
      </div>
    </div>
  );
}

export default function App() {
  return <BentoHero />;
}
