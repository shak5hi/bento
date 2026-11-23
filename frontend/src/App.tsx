import { useEffect, useRef, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, Lightformer } from '@react-three/drei';
import * as THREE from 'three';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useNavigate } from 'react-router-dom';
import { AnimationController } from './experience/animations/AnimationController';
import { BentoModel } from './experience/models/BentoModel';
import { heroScroll } from './experience/scrollState';
import { DashboardPreview } from './landing/DashboardPreview';
import { LandingNav, LandingSections } from './landing/Sections';
import { auth } from './lib/api';
import './HeroLayout.css';
import './landing/Landing.css';

gsap.registerPlugin(ScrollTrigger);

type ZoomKey = 'comp1ZoomProgress' | 'zoomProgress' | 'comp3ZoomProgress' | 'comp4ZoomProgress' | 'comp5ZoomProgress';

/** The five chapters of the scroll story, one per compartment (camera framing in AnimationController). */
const CHAPTERS: { zoom: ZoomKey; eyebrow: string; title: React.ReactNode; body: string; side: 'l' | 'r' }[] = [
  { zoom: 'comp1ZoomProgress', eyebrow: '01 · Balance', title: <>Every bento needs <b>balance.</b></>, body: 'Every engineering portfolio does too. Pickle quietly brings together signals from every project and turns them into calm, actionable guidance.', side: 'r' },
  { zoom: 'zoomProgress', eyebrow: '02 · Habit', title: <>Healthy projects are <b>built daily.</b></>, body: 'Bento helps you make steady progress by focusing on the work that matters most — three things today, not fifty alerts.', side: 'l' },
  { zoom: 'comp3ZoomProgress', eyebrow: '03 · Health', title: <>See beyond <b>the code.</b></>, body: 'Every project receives a living Engineering Health Score: a picture of its quality, not just its activity.', side: 'r' },
  { zoom: 'comp4ZoomProgress', eyebrow: '04 · Everything', title: <>Bring everything <b>to the table.</b></>, body: 'Bento gathers every project into one place, giving you a complete view of your engineering world.', side: 'l' },
  { zoom: 'comp5ZoomProgress', eyebrow: '05 · Signal', title: <>Every signal tells <b>a story.</b></>, body: 'Bento brings them together into clear recommendations you can actually act on.', side: 'r' },
];

// Timeline (abstract units across the 800vh pin)
const OPEN_AT = 50;
const OPEN_FOR = 70; // the lid takes its time
const CHAPTER_AT = OPEN_AT + OPEN_FOR + 10;
const CHAPTER_EVERY = 100;
const CLOSE_AT = CHAPTER_AT + CHAPTERS.length * CHAPTER_EVERY;

function BentoHero() {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const rightColRef = useRef<HTMLDivElement>(null);
  const scrollHintRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const finalTextLeftRef = useRef<HTMLDivElement>(null);
  const finalTextRightRef = useRef<HTMLDivElement>(null);
  const previewRef = useRef<HTMLDivElement>(null);
  const chapterRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scrimLRef = useRef<HTMLDivElement>(null);
  const scrimRRef = useRef<HTMLDivElement>(null);

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
        },
      });

      tl.to({}, { duration: 1400 });

      tl.to([leftColRef.current, scrollHintRef.current], { xPercent: -80, opacity: 0, ease: 'power2.inOut', duration: 10 }, 10);

      const camProxy = { progress: 0 };
      tl.to(camProxy, {
        progress: 1, ease: 'power3.inOut', duration: 28,
        onUpdate: () => { heroScroll.cameraProgress = camProxy.progress; },
      }, 20);

      tl.to(rightColRef.current, {
        x: () => {
          const parent = rightColRef.current!.parentElement;
          if (!parent) return 0;
          const style = window.getComputedStyle(parent);
          const contentWidth = parent.getBoundingClientRect().width - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
          return -0.26 * contentWidth;
        },
        ease: 'power3.inOut', duration: 28,
      }, 20);

      // Lid opens (easing lives in BentoModel / AnimationController, so keep this linear)
      const open = { progress: 0 };
      tl.to(open, { progress: 1, ease: 'none', duration: OPEN_FOR, onUpdate: () => { heroScroll.rawProgress = open.progress; } }, OPEN_AT);

      // Chapters: camera pushes into a compartment, its story fades in, then pulls back out.
      CHAPTERS.forEach((ch, i) => {
        const at = CHAPTER_AT + i * CHAPTER_EVERY;
        const z = { p: 0 };
        const text = chapterRefs.current[i];
        const scrim = ch.side === 'l' ? scrimLRef.current : scrimRRef.current;
        tl.to(z, { p: 1, ease: 'power3.inOut', duration: 30, onUpdate: () => { heroScroll[ch.zoom] = z.p; } }, at);
        tl.to(overlayRef.current, { opacity: 1, ease: 'power2.inOut', duration: 8 }, at + 18);
        tl.to(scrim, { opacity: 1, ease: 'power2.out', duration: 14 }, at + 20);
        tl.to(text, { opacity: 1, y: 0, ease: 'power3.out', duration: 15 }, at + 25);
        tl.to(text, { opacity: 0, y: 40, ease: 'power3.in', duration: 10 }, at + 60);
        tl.to(scrim, { opacity: 0, ease: 'power2.in', duration: 12 }, at + 60);
        tl.to(overlayRef.current, { opacity: 0, ease: 'power3.inOut', duration: 15 }, at + 60);
        tl.to(z, { p: 0, ease: 'power3.inOut', duration: 30, onUpdate: () => { heroScroll[ch.zoom] = z.p; } }, at + 60);
      });

      // Lid goes back on
      const close = { progress: 1 };
      tl.to(close, { progress: 0, ease: 'none', duration: 120, onUpdate: () => { heroScroll.rawProgress = close.progress; } }, CLOSE_AT);

      tl.fromTo(finalTextLeftRef.current, { x: -300, opacity: 0 }, { x: 0, opacity: 1, ease: 'power2.out', duration: 150 }, CLOSE_AT + 120);
      tl.fromTo(finalTextRightRef.current, { x: 300, opacity: 0 }, { x: 0, opacity: 1, ease: 'power2.out', duration: 150 }, CLOSE_AT + 120);

      tl.to(rightColRef.current, { x: () => -1.5 * window.innerWidth, ease: 'power2.inOut', duration: 120 }, CLOSE_AT + 320);

      tl.fromTo(previewRef.current,
        { xPercent: -50, yPercent: 150, opacity: 0 },
        { yPercent: -50, opacity: 1, ease: 'power3.out', duration: 150 },
        CLOSE_AT + 540,
      );
    });

    return () => ctx.revert();
  }, []);

  const scrollToStory = () => window.scrollTo({ top: window.innerHeight * 1.6, behavior: 'smooth' });
  const getStarted = () => navigate(auth.token ? '/dashboard' : '/login');

  return (
    <div className="hero-container" ref={containerRef} id="top">
      <div className="hero-content">
        <div className="hero-left-col" ref={leftColRef}>
          <p className="hero-kicker">The engineering home for everything you build</p>
          <h1 className="heading">Every project deserves a place at <b>the table.</b></h1>
          <p className="paragraph">Bento watches every project you own — uptime, code health, dependencies — and tells you what deserves your attention today.</p>
          <div className="cta-group">
            <button className="btn-primary" onClick={getStarted}>Get started</button>
            <button className="btn-secondary" onClick={scrollToStory}>Open the box <span aria-hidden="true">↓</span></button>
          </div>
        </div>

        <div className="hero-right-col" ref={rightColRef}>
          <Canvas
            shadows
            camera={{ position: [-26.011, 13.694, 5.51], fov: 20 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, outputColorSpace: THREE.SRGBColorSpace }}
            className="hero-canvas"
          >
            <AnimationController />
            <ambientLight intensity={0.45} />
            <directionalLight
              castShadow
              position={[-7, 16, 9]}
              intensity={2.4}
              color="#fff4e8"
              shadow-mapSize={[2048, 2048]}
              shadow-camera-left={-10}
              shadow-camera-right={10}
              shadow-camera-top={10}
              shadow-camera-bottom={-10}
              shadow-camera-near={1}
              shadow-camera-far={50}
              shadow-bias={-0.0003}
              shadow-normalBias={0.02}
            />
            <directionalLight position={[9, 5, -7]} intensity={0.8} color="#ffcfb0" />
            {/* studio reflections for the lacquer, generated locally (no HDR download) */}
            <Environment resolution={256} frames={1}>
              <Lightformer form="rect" intensity={1.6} position={[-5, 9, 3]} rotation-x={Math.PI / 2} rotation-z={0.6} scale={[2.2, 16, 1]} />
              <Lightformer form="rect" intensity={0.9} color="#ffe6d2" position={[-8, 4, 6]} rotation-y={Math.PI / 3} scale={[8, 3, 1]} />
              <Lightformer form="rect" intensity={0.6} color="#ffb48a" position={[8, 3, -6]} rotation-y={-Math.PI / 3} scale={[6, 2, 1]} />
            </Environment>
            <Suspense fallback={null}>
              <BentoModel />
            </Suspense>
          </Canvas>
        </div>
      </div>

      <div className="scroll-hint" ref={scrollHintRef}>Scroll to open</div>
      <div ref={overlayRef} className="story-overlay" />
      {/* keeps chapter text legible over the food */}
      <div ref={scrimLRef} className="story-scrim story-scrim-l" />
      <div ref={scrimRRef} className="story-scrim story-scrim-r" />

      {CHAPTERS.map((ch, i) => (
        <div key={ch.eyebrow} ref={(el) => { chapterRefs.current[i] = el; }} className={`story-text story-text-${ch.side}`}>
          <p className="story-eyebrow">{ch.eyebrow}</p>
          <h2 className="story-heading">{ch.title}</h2>
          <p className="story-p">{ch.body}</p>
        </div>
      ))}

      <div ref={finalTextLeftRef} className="final-text final-text-l">
        <h2 className="final-heading">Everything you build.</h2>
      </div>
      <div ref={finalTextRightRef} className="final-text final-text-r">
        <h2 className="final-heading"><b>One engineering home.</b></h2>
      </div>

      <DashboardPreview ref={previewRef} />
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
      <LandingNav />
      <BentoHero />
      <LandingSections />
      <Footer />
    </div>
  );
}
