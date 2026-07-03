import { useEffect, useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import * as THREE from 'three';
import logoSrc from './assets/logo.png';
import zoom1Img from './assets/compartmentzoom1.svg';
import zoom2Img from './assets/compartmentzoom2.svg';
import zoom3Img from './assets/Compartment3.svg';
import zoom4Img from './assets/compartmentzoom4.svg';
import zoom5Img from './assets/Compartment5.svg';
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
  
  const zoom1Ref = useRef<HTMLImageElement>(null);
  const zoom1TextRef = useRef<HTMLDivElement>(null);
  const zoom2Ref = useRef<HTMLImageElement>(null);
  const zoomTextRef = useRef<HTMLDivElement>(null);
  const zoom3Ref = useRef<HTMLImageElement>(null);
  const zoom3TextRef = useRef<HTMLDivElement>(null);
  const zoom4Ref = useRef<HTMLImageElement>(null);
  const zoom4TextRef = useRef<HTMLDivElement>(null);
  const zoom5Ref = useRef<HTMLImageElement>(null);
  const zoom5TextRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !leftColRef.current || !rightColRef.current) return;

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: containerRef.current,
          start: 'top top',
          end: 'bottom bottom',
          scrub: 2.5,
          invalidateOnRefresh: true,
        }
      });

      tl.to({}, { duration: 750 });

      tl.to([leftColRef.current, scrollHintRef.current], {
        xPercent: -80, opacity: 0, ease: 'power2.inOut', duration: 10
      }, 10);

      const camProxy = { progress: 0 };
      tl.to(camProxy, {
        progress: 1, ease: 'power3.inOut', duration: 28,
        onUpdate: () => { heroScroll.cameraProgress = camProxy.progress; }
      }, 20);

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
        ease: 'power3.inOut', duration: 28
      }, 20);

      const proxy = { progress: 0 };
      tl.to(proxy, {
        progress: 1, ease: 'none', duration: 50,
        onUpdate: () => { heroScroll.rawProgress = proxy.progress; }
      }, 50);

      // --- COMPARTMENT 1 ---
      const zs1 = { p: 0 };
      tl.to(zs1, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp1ZoomProgress = zs1.p }, 110);
      tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 5 }, 130);
      tl.to([zoom1Ref.current, zoom1TextRef.current], { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, 135);
      tl.to([zoom1Ref.current, zoom1TextRef.current], { opacity: 0, y: 50, ease: 'power3.in', duration: 10 }, 170);
      tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, 170);
      tl.to(zs1, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp1ZoomProgress = zs1.p }, 170);

      // --- COMPARTMENT 2 ---
      const zs2 = { p: 0 };
      tl.to(zs2, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.zoomProgress = zs2.p }, 210);
      tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 5 }, 230);
      tl.to([zoom2Ref.current, zoomTextRef.current], { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, 235);
      tl.to([zoom2Ref.current, zoomTextRef.current], { opacity: 0, y: 50, ease: 'power3.in', duration: 10 }, 270);
      tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, 270);
      tl.to(zs2, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.zoomProgress = zs2.p }, 270);

      // --- COMPARTMENT 3 ---
      const zs3 = { p: 0 };
      tl.to(zs3, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp3ZoomProgress = zs3.p }, 310);
      tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 5 }, 330);
      tl.to([zoom3Ref.current, zoom3TextRef.current], { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, 335);
      tl.to([zoom3Ref.current, zoom3TextRef.current], { opacity: 0, y: 50, ease: 'power3.in', duration: 10 }, 370);
      tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, 370);
      tl.to(zs3, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp3ZoomProgress = zs3.p }, 370);

      // --- COMPARTMENT 4 ---
      const zs4 = { p: 0 };
      tl.to(zs4, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp4ZoomProgress = zs4.p }, 410);
      tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 5 }, 430);
      tl.to([zoom4Ref.current, zoom4TextRef.current], { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, 435);
      tl.to([zoom4Ref.current, zoom4TextRef.current], { opacity: 0, y: 50, ease: 'power3.in', duration: 10 }, 470);
      tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, 470);
      tl.to(zs4, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp4ZoomProgress = zs4.p }, 470);

      // --- COMPARTMENT 5 ---
      const zs5 = { p: 0 };
      tl.to(zs5, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp5ZoomProgress = zs5.p }, 510);
      tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 5 }, 530);
      tl.to([zoom5Ref.current, zoom5TextRef.current], { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, 535);
      tl.to([zoom5Ref.current, zoom5TextRef.current], { opacity: 0, y: 50, ease: 'power3.in', duration: 10 }, 570);
      tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, 570);
      tl.to(zs5, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => heroScroll.comp5ZoomProgress = zs5.p }, 570);

      // --- CLOSE LID ---
      const proxyClose = { progress: 1 };
      tl.to(proxyClose, {
        progress: 0, ease: 'power2.inOut', duration: 50,
        onUpdate: () => { heroScroll.rawProgress = proxyClose.progress; }
      }, 610);

    });

    return () => ctx.revert();
  }, []);

  const leftLayoutImg = { position: "fixed", top: "2vh", right: "-18vw", width: "65vw", opacity: 0, transform: "translateY(100px)", zIndex: 10, pointerEvents: "none" };
  const leftLayoutText = { position: "fixed", top: "12vh", left: "4vw", width: "60vw", opacity: 0, transform: "translateY(50px)", zIndex: 10, pointerEvents: "none", color: "#fff", fontFamily: "\"Arial Black\", Impact, system-ui, -apple-system, sans-serif" };

  const rightLayoutImg = { position: "fixed", top: "-5vh", left: "-15vw", width: "60vw", opacity: 0, transform: "translateY(100px)", zIndex: 10, pointerEvents: "none" };
  const rightLayoutText = { position: "fixed", bottom: "12vh", right: "4vw", width: "60vw", opacity: 0, transform: "translateY(50px)", zIndex: 10, pointerEvents: "none", color: "#fff", fontFamily: "\"Arial Black\", Impact, system-ui, -apple-system, sans-serif", textAlign: "right", display: "flex", flexDirection: "column", alignItems: "flex-end" };

  const headingStyle = { fontSize: "clamp(3.5rem, 5.5vw, 6.5rem)", fontWeight: 900, lineHeight: 0.85, letterSpacing: "-0.04em", textTransform: "uppercase", margin: 0, marginBottom: "1.5rem", color: "#fff", whiteSpace: "nowrap" };
  const pStyle = { fontFamily: "\"Inter\", system-ui, -apple-system, sans-serif", fontSize: "1.25rem", lineHeight: 1.5, fontWeight: 400, color: "rgba(255, 255, 255, 0.9)", maxWidth: "45ch", letterSpacing: "0.01em", whiteSpace: "normal" };

  return (
    <div className="hero-container" ref={containerRef}>
      <div className="hero-content">
        <div className="hero-left-col" ref={leftColRef}>
          <div className="logo"><img src={logoSrc} alt="Bento" className="logo-img" /></div>
          <h1 className="heading">Every project deserves<br />a place at<br />the table.</h1>
          <p className="paragraph">One beautiful place.<br />A workspace designed for clarity —<br />no clutter, just your best work.</p>
          <div className="cta-group">
            <button className="btn-primary">Get Started</button>
            <button className="btn-secondary">See how it works →</button>
          </div>
        </div>

        <div className="hero-right-col" ref={rightColRef}>
          <Canvas shadows camera={{ position: [-26.011, 13.694, 5.510], fov: 20 }} dpr={[1, 2]} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, outputColorSpace: THREE.SRGBColorSpace }} className="hero-canvas">
            <AnimationController />
            <Suspense fallback={null}>
              <ambientLight intensity={1.8} />
              <directionalLight position={[-8, 10, 5]} intensity={3.6} color="#fff5ee" />
              <directionalLight position={[5, 4, -4]} intensity={1.1} color="#ffffff" />
              <BentoModel />
            </Suspense>
          </Canvas>
        </div>
      </div>

      <div className="scroll-hint" ref={scrollHintRef}>Scroll to open</div>
      <div ref={overlayRef} style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", backgroundColor: "#A13920", opacity: 0, pointerEvents: "none", zIndex: 0 }} />

      {/* COMPARTMENT 1 - Right Layout */}
      <img src={zoom1Img} ref={zoom1Ref} style={rightLayoutImg as any} />
      <div ref={zoom1TextRef} style={rightLayoutText as any}>
        <h2 style={headingStyle as any}>EVERY<br/>BENTO NEEDS<br/>BALANCE.</h2>
        <p style={pStyle as any}>Every engineering portfolio does too. Pickle quietly brings together signals from every project and turns them into calm, actionable guidance.</p>
      </div>

      {/* COMPARTMENT 2 - Left Layout */}
      <img src={zoom2Img} ref={zoom2Ref} style={leftLayoutImg as any} />
      <div ref={zoomTextRef} style={leftLayoutText as any}>
        <h2 style={headingStyle as any}>HEALTHY<br/>PROJECTS<br/>ARE BUILT<br/>DAILY.</h2>
        <p style={pStyle as any}>Bento helps you make steady progress by focusing on the work that matters most.</p>
      </div>

      {/* COMPARTMENT 3 - Right Layout */}
      <img src={zoom3Img} ref={zoom3Ref} style={rightLayoutImg as any} />
      <div ref={zoom3TextRef} style={rightLayoutText as any}>
        <h2 style={headingStyle as any}>SEE<br/>BEYOND<br/>THE CODE.</h2>
        <p style={pStyle as any}>Every project receives a living Engineering Health Score, giving you a complete picture of its quality, not just its activity.</p>
      </div>

      {/* COMPARTMENT 4 - Left Layout */}
      <img src={zoom4Img} ref={zoom4Ref} style={leftLayoutImg as any} />
      <div ref={zoom4TextRef} style={leftLayoutText as any}>
        <h2 style={headingStyle as any}>BRING<br/>EVERYTHING<br/>TO THE<br/>TABLE.</h2>
        <p style={pStyle as any}>Bento gathers every project into one place, giving you a complete view of your engineering world.</p>
      </div>

      {/* COMPARTMENT 5 - Right Layout */}
      <img src={zoom5Img} ref={zoom5Ref} style={rightLayoutImg as any} />
      <div ref={zoom5TextRef} style={rightLayoutText as any}>
        <h2 style={headingStyle as any}>EVERY<br/>SIGNAL TELLS<br/>A STORY.</h2>
        <p style={pStyle as any}>Bento brings them together into clear recommendations you can actually act on.</p>
      </div>
    </div>
  );
}

export default function App() { return <BentoHero />; }
