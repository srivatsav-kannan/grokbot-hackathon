import { useLayoutEffect, useRef } from "react";
import { mediaUrl } from "../api/client";
import { gsap, ScrollTrigger, useReducedMotion } from "../lib/scroll";
import type { ListingCard } from "../types";

const WORDS = ["Bikes", "Computers", "Furniture", "Priced", "Checked"];

export function Hero({ listings }: { listings: ListingCard[] }) {
  const root = useRef<HTMLElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  const cells =
    listings.length > 0
      ? listings.map((listing) => ({
          key: listing.id,
          label: listing.title,
          src: listing.photos[0] ? mediaUrl(listing.photos[0]) : "",
        }))
      : WORDS.map((word) => ({ key: word, label: word, src: "" }));
  const loop = reduced ? cells : [...cells, ...cells];

  useLayoutEffect(() => {
    const section = root.current;
    const rail = track.current;
    if (!section || !rail || reduced) return;
    const ctx = gsap.context(() => {
      gsap.to(rail, {
        xPercent: -50,
        ease: "none",
        scrollTrigger: {
          trigger: section,
          start: "top bottom",
          end: "bottom top",
          scrub: true,
        },
      });
    }, section);
    ScrollTrigger.refresh();
    return () => ctx.revert();
  }, [reduced, listings]);

  return (
    <section className="hero" ref={root} aria-labelledby="hero-title">
      <div className="wrap hero-copy">
        <h1 id="hero-title">Bay Area bikes, computers, and furniture.</h1>
        <p>
          Each listing is priced against comps and checked for trust before it reaches the board.
          Search in your own words. The buyer agent can negotiate from the same sentence.
        </p>
      </div>
      <div className={reduced ? "rail rail-static" : "rail"} aria-hidden="true">
        <div className="rail-track" ref={track}>
          {loop.map((cell, index) => (
            <span className="rail-item" key={`${cell.key}-${index}`}>
              {cell.src ? (
                <img src={cell.src} alt="" width={800} height={600} />
              ) : null}
              <span>{cell.label}</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
