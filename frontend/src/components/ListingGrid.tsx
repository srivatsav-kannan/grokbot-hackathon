import { useLayoutEffect, useRef } from "react";
import { gsap, ScrollTrigger, useReducedMotion } from "../lib/scroll";
import { ListingCard } from "./ListingCard";
import type { ListingCard as Listing } from "../types";

export function ListingGrid({ listings }: { listings: Listing[] }) {
  const root = useRef<HTMLUListElement>(null);
  const reduced = useReducedMotion();

  useLayoutEffect(() => {
    const scope = root.current;
    if (!scope || reduced || listings.length === 0) return;
    const ctx = gsap.context(() => {
      ScrollTrigger.batch(".lot-photo img", {
        start: "top 92%",
        once: true,
        onEnter: (batch) => {
          gsap.from(batch, {
            clipPath: "inset(16% 0 0 0)",
            duration: 0.55,
            stagger: 0.05,
            ease: "power2.out",
            overwrite: "auto",
          });
        },
      });
    }, scope);
    return () => ctx.revert();
  }, [listings, reduced]);

  return (
    <ul className="lots" id="listing-grid" ref={root}>
      {listings.map((listing, index) => (
        <ListingCard key={listing.id} listing={listing} index={index} />
      ))}
    </ul>
  );
}
