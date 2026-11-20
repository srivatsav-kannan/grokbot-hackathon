import { mediaUrl } from "../api/client";
import { isPlaceholderSrc } from "./PhotoFrame";
import { useReducedMotion } from "../lib/scroll";
import type { ListingCard } from "../types";

export function Hero({ listings }: { listings: ListingCard[] }) {
  const reduced = useReducedMotion();
  const cells = listings.slice(0, 8).map((listing) => ({
    key: listing.id,
    label: listing.title,
    src: listing.photos[0] ? mediaUrl(listing.photos[0]) : "",
  }));
  const loop = reduced || cells.length === 0 ? cells : [...cells, ...cells];

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap hero-copy">
        <h1 id="hero-title">Bay Area bikes, computers, and furniture.</h1>
        <p>Search the board, or send a buyer bot that keeps looking and talks to Fairlot sellers.</p>
      </div>
      {loop.length > 0 ? (
        <div className={reduced ? "rail rail-static" : "rail"} aria-hidden="true">
          <div className="rail-track">
            {loop.map((cell, index) => (
              <span className="rail-item" key={`${cell.key}-${index}`}>
                {cell.src ? (
                  <img
                    className={isPlaceholderSrc(cell.src) ? "rail-pending" : undefined}
                    src={cell.src}
                    alt=""
                    width={152}
                    height={114}
                  />
                ) : null}
                <span>{cell.label}</span>
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
