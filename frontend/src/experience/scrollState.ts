/**
 * heroScroll — shared mutable singleton.
 *
 * Written once per frame by the GSAP ScrollTrigger onUpdate in App.tsx.
 * Read every frame by BentoModel's useFrame hook.
 *
 * Deliberately NOT React state — we never want a re-render from scroll.
 */
export const heroScroll = {
  /** Normalised scroll progress through the hero sequence: 0 (top) → 1 (end of pin). */
  rawProgress: 0,
  cameraProgress: 0,
  zoomProgress: 0,
  comp1ZoomProgress: 0,
  comp3ZoomProgress: 0,
  comp4ZoomProgress: 0,
  comp5ZoomProgress: 0,
  fadeProgress: 0,
};
