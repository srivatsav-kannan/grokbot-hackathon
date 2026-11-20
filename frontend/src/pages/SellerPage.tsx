import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getSeller } from "../api/client";
import { ListingGrid } from "../components/ListingGrid";
import { DetailSkeleton, ErrorNotice } from "../components/States";
import { useTitle } from "../lib/title";
import type { SellerProfile } from "../types";

export function SellerPage() {
  const { id = "" } = useParams();
  const [seller, setSeller] = useState<SellerProfile | null>(null);
  const [error, setError] = useState("");
  useTitle(seller ? seller.name : "Seller");

  useEffect(() => {
    const controller = new AbortController();
    setSeller(null);
    setError("");
    getSeller(id, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setSeller(payload);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof ApiError ? err.message : "This seller didn't load.");
      });
    return () => controller.abort();
  }, [id]);

  if (error) {
    return (
      <div className="wrap board">
        <ErrorNotice title="Seller" message={error} onRetry={() => window.location.reload()} />
      </div>
    );
  }
  if (!seller) {
    return (
      <div className="wrap board">
        <DetailSkeleton />
      </div>
    );
  }

  const joined = new Date(seller.joined).toLocaleDateString(undefined, { month: "long", year: "numeric" });
  return (
    <div className="wrap board seller-page">
      <p className="back-row">
        <Link className="back-link" to="/">
          Back to the board
        </Link>
      </p>
      <header className="seller-head">
        <span className="seller-avatar" aria-hidden="true">
          {seller.name.slice(0, 1)}
        </span>
        <div>
          <h1>{seller.name}</h1>
          <p className="offer-hint">
            {seller.area ? `${seller.area} · ` : ""}On Fairlot since {joined} · {seller.listings.length} for sale ·{" "}
            {seller.sold_count} sold
          </p>
          {seller.bio ? <p>{seller.bio}</p> : null}
        </div>
      </header>
      <h2 className="section-title">For sale</h2>
      {seller.listings.length > 0 ? <ListingGrid listings={seller.listings} /> : <p>Nothing for sale right now.</p>}
    </div>
  );
}
