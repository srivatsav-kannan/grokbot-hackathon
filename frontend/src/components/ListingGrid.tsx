import { ListingCard } from "./ListingCard";
import type { ListingCard as Listing } from "../types";

export function ListingGrid({ listings }: { listings: Listing[] }) {
  return (
    <ul className="lots" id="listing-grid">
      {listings.map((listing, index) => (
        <ListingCard key={listing.id} listing={listing} index={index} />
      ))}
    </ul>
  );
}
