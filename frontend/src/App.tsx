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
import mockDashboardImg from './assets/mockdashboard.png';
import './HeroLayout.css';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useNavigate } from 'react-router-dom';
import { heroScroll } from './experience/scrollState';
import { auth } from './lib/api';

gsap.registerPlugin(ScrollTrigger);

function BentoHero() {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const rightColRef = useRef<HTMLDivElement>(null);
  const scrollHintRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  
  const finalTextLeftRef = useRef<HTMLDivElement>(null);
  const finalTextRightRef = useRef<HTMLDivElement>(null);
  const mockDashboardRef = useRef<HTMLImageElement>(null);
  
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

      tl.to({}, { duration: 1400 });

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

      // --- CLOSE LID AND SLIDE OUT ---
      const proxyClose = { progress: 1 };
      tl.to(proxyClose, {
        progress: 0, ease: 'power2.inOut', duration: 120, // Close completely
        onUpdate: () => { heroScroll.rawProgress = proxyClose.progress; }
      }, 610);

      // --- TEXT APPEARS ---
      tl.fromTo(finalTextLeftRef.current,
        { x: -300, opacity: 0 },
        { x: 0, opacity: 1, ease: 'power2.out', duration: 150 }, // Slowed down by tripling duration
        730
      );
      tl.fromTo(finalTextRightRef.current,
        { x: 300, opacity: 0 },
        { x: 0, opacity: 1, ease: 'power2.out', duration: 150 }, // Slowed down
        730
      );

      // --- WAIT A SPLIT SEC, THEN SLIDE OUT ---
      tl.to(rightColRef.current, {
        x: () => -1.5 * window.innerWidth, // Slide out left
        ease: 'power2.inOut', duration: 120
      }, 930); // Starts at 930 (730 + 150 text anim + 50 wait), Ends at 1050

      // --- MOCK DASHBOARD APPEARS ---
      tl.fromTo(mockDashboardRef.current,
        { xPercent: -50, yPercent: 150, opacity: 0 },
        { yPercent: -50, opacity: 1, ease: 'power3.out', duration: 150 },
        1150 // Wait 100 units after bento box is completely gone
      );

    });

    return () => ctx.revert();
  }, []);

  const scrollToStory = () => window.scrollTo({ top: window.innerHeight * 1.6, behavior: 'smooth' });
  const getStarted = () => navigate(auth.token ? '/dashboard' : '/login');

  return (
    <div className="hero-container" ref={containerRef}>
      <div className="hero-content">
        <div className="hero-left-col" ref={leftColRef}>
          <div className="logo"><img src={logoSrc} alt="Bento" className="logo-img" /></div>
          <h1 className="heading">Every project deserves a place at <b>the table.</b></h1>
          <p className="paragraph">One calm place for everything you build. Bento watches every project you own and tells you what deserves your attention today.</p>
          <div className="cta-group">
            <button className="btn-primary" onClick={getStarted}>Get started</button>
            <button className="btn-secondary" onClick={scrollToStory}>See how it works <span aria-hidden="true">↓</span></button>
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
      <div ref={overlayRef} className="story-overlay" />

      {/* COMPARTMENT 1 - Right Layout */}
      <img src={zoom1Img} ref={zoom1Ref} className="story-img story-img-r" alt="" />
      <div ref={zoom1TextRef} className="story-text story-text-r">
        <p className="story-eyebrow">01 · Balance</p>
        <h2 className="story-heading">Every bento needs <b>balance.</b></h2>
        <p className="story-p">Every engineering portfolio does too. Pickle quietly brings together signals from every project and turns them into calm, actionable guidance.</p>
      </div>

      {/* COMPARTMENT 2 - Left Layout */}
      <img src={zoom2Img} ref={zoom2Ref} className="story-img story-img-l" alt="" />
      <div ref={zoomTextRef} className="story-text story-text-l">
        <p className="story-eyebrow">02 · Habit</p>
        <h2 className="story-heading">Healthy projects are <b>built daily.</b></h2>
        <p className="story-p">Bento helps you make steady progress by focusing on the work that matters most — three things today, not fifty alerts.</p>
      </div>

      {/* COMPARTMENT 3 - Right Layout */}
      <img src={zoom3Img} ref={zoom3Ref} className="story-img story-img-r" alt="" />
      <div ref={zoom3TextRef} className="story-text story-text-r">
        <p className="story-eyebrow">03 · Health</p>
        <h2 className="story-heading">See beyond <b>the code.</b></h2>
        <p className="story-p">Every project receives a living Engineering Health Score: a picture of its quality, not just its activity.</p>
      </div>

      {/* COMPARTMENT 4 - Left Layout */}
      <img src={zoom4Img} ref={zoom4Ref} className="story-img story-img-l" alt="" />
      <div ref={zoom4TextRef} className="story-text story-text-l">
        <p className="story-eyebrow">04 · Everything</p>
        <h2 className="story-heading">Bring everything <b>to the table.</b></h2>
        <p className="story-p">Bento gathers every project into one place, giving you a complete view of your engineering world.</p>
      </div>

      {/* COMPARTMENT 5 - Right Layout */}
      <img src={zoom5Img} ref={zoom5Ref} className="story-img story-img-r" alt="" />
      <div ref={zoom5TextRef} className="story-text story-text-r">
        <p className="story-eyebrow">05 · Signal</p>
        <h2 className="story-heading">Every signal tells <b>a story.</b></h2>
        <p className="story-p">Bento brings them together into clear recommendations you can actually act on.</p>
      </div>

      {/* FINAL SEQUENCE TEXTS */}
      <div ref={finalTextLeftRef} className="final-text final-text-l">
        <h2 className="final-heading">Everything you build.</h2>
      </div>
      <div ref={finalTextRightRef} className="final-text final-text-r">
        <h2 className="final-heading"><b>One engineering home.</b></h2>
      </div>

      {/* MOCK DASHBOARD */}
      <img ref={mockDashboardRef} src={mockDashboardImg} className="mock-dashboard" alt="The Bento dashboard" />
    </div>
  );
}

function Footer() {
  const cols = [
    { title: 'Product', links: ['How it works', 'Health score', 'Pickle', 'Changelog'] },
    { title: 'Company', links: ['About', 'Careers', 'Blog', 'Contact'] },
    { title: 'Legal', links: ['Privacy', 'Terms'] },
  ];
  return (
    <footer className="site-footer">
      <div className="footer-top">
        <div>
          <p className="footer-brand">Bento</p>
          <p className="footer-tag">One engineering home.<br />Stop guessing. Start growing.</p>
        </div>
        <nav className="footer-cols" aria-label="Footer">
          {cols.map((c) => (
            <div key={c.title}>
              <p className="footer-h">{c.title}</p>
              <ul>{c.links.map((l) => <li key={l}><a href="#">{l}</a></li>)}</ul>
            </div>
          ))}
        </nav>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} Bento</span>
        <span className="footer-social"><a href="#">X</a><a href="#">LinkedIn</a><a href="#">GitHub</a></span>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <div className="landing">
      <BentoHero />
      <Footer />
    </div>
  );
}
