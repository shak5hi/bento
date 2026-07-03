import { useEffect } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { lidRef } from '../refs/bentoRefs';

gsap.registerPlugin(ScrollTrigger);

export function useLidAnimation(scrollContainer: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    // Wait a tick for the R3F scene to mount and bounding-box math to run
    const timer = setTimeout(() => {
      // TEMPORARILY DISABLED FOR MANUAL LEVA CALIBRATION
      return;
      
      const lid = lidRef.current;
      if (!lid || !scrollContainer.current) return;

      // Capture the CLOSED position (whatever the auto-close math set it to)
      const closedY = lid.position.y;
      const closedX = lid.position.x;

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: scrollContainer.current,
          start: 'top top',
          end: '50% top',
          scrub: 2,       // heavy scrub = weighted, mechanical feel
        },
      });

      // Phase 1: Lift straight UP from closed position
      tl.to(lid.position, {
        y: closedY + 3.5,
        duration: 0.5,
        ease: 'power1.inOut',
      })
      // Phase 2: Slide LEFT and settle
      .to(lid.position, {
        x: closedX - 7,
        y: closedY + 1.5,
        duration: 1,
        ease: 'power2.out',
      });
    }, 600);

    return () => {
      clearTimeout(timer);
      ScrollTrigger.getAll().forEach((t) => t.kill());
    };
  }, []);
}
