import { useEffect, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";

gsap.registerPlugin(ScrollTrigger);

let lenis: Lenis | null = null;
let ticker: ((time: number) => void) | null = null;

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  return reduced;
}

function smoothScrollAllowed(): boolean {
  return (
    window.matchMedia("(pointer: fine)").matches &&
    window.matchMedia("(min-width: 800px)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function startSmoothScroll(): void {
  stopSmoothScroll();
  if (!smoothScrollAllowed()) return;
  lenis = new Lenis({
    lerp: 0.12,
    smoothWheel: true,
    anchors: true,
  });
  lenis.on("scroll", ScrollTrigger.update);
  ticker = (time: number) => {
    lenis?.raf(time * 1000);
  };
  gsap.ticker.add(ticker);
  gsap.ticker.lagSmoothing(0);
}

export function stopSmoothScroll(): void {
  if (ticker) {
    gsap.ticker.remove(ticker);
    ticker = null;
  }
  lenis?.destroy();
  lenis = null;
  gsap.ticker.lagSmoothing(500);
}

export function scrollToTop(): void {
  if (lenis) {
    lenis.scrollTo(0, { immediate: true });
    return;
  }
  window.scrollTo(0, 0);
}

export { gsap, ScrollTrigger };
