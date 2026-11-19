import { Link } from "react-router-dom";
import { mediaUrl } from "../api/client";
import { CATEGORY_LABEL } from "../lib/format";
import type { ListingCard as Listing } from "../types";
import { Marks } from "./Marks";
import { PhotoFrame } from "./PhotoFrame";
import { Price } from "./Price";

export function ListingCard({ listing, index }: { listing: Listing; index: number }) {
  const photo = listing.photos[0] ? mediaUrl(listing.photos[0]) : "";
  const category = CATEGORY_LABEL[listing.category];

  return (
    <li
      className="lot"
      id={`listing-${listing.id}`}
      data-listing-id={listing.id}
      data-category={listing.category}
      data-price={listing.price}
      data-verdict={listing.appraisal.verdict}
      data-trust={listing.inspection.trust_level}
      data-origin={listing.origin}
      data-neighborhood={listing.neighborhood}
    >
      <Link className="lot-link" to={`/listings/${listing.id}`}>
        <PhotoFrame src={photo} alt="" label={category} eager={index < 4} />
        <Price amount={listing.price} />
        <h2 className="lot-title">{listing.title}</h2>
        <p className="lot-place">{listing.neighborhood}</p>
        <Marks
          verdict={listing.appraisal.verdict}
          trust={listing.inspection.trust_level}
          origin={listing.origin}
        />
      </Link>
    </li>
  );
}
