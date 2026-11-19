import type { ReactNode } from "react";

export function LoadingGrid({ label }: { label: string }) {
  return (
    <div className="state" aria-busy="true" aria-live="polite">
      <p className="sr-only">{label}</p>
      <ul className="lots" aria-hidden="true">
        {Array.from({ length: 8 }, (_, index) => (
          <li className="skeleton" key={index}>
            <span className="skeleton-photo" />
            <span className="skeleton-line skeleton-price" />
            <span className="skeleton-line" />
            <span className="skeleton-line skeleton-short" />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="state detail-skeleton" aria-busy="true" aria-live="polite">
      <p className="sr-only">Loading listing</p>
      <div className="detail-top" aria-hidden="true">
        <span className="skeleton-photo skeleton-photo-lg" />
        <div>
          <span className="skeleton-line skeleton-price" />
          <span className="skeleton-line" />
          <span className="skeleton-line" />
          <span className="skeleton-line skeleton-short" />
        </div>
      </div>
    </div>
  );
}

export function TranscriptSkeleton() {
  return (
    <div className="state" aria-busy="true" aria-live="polite">
      <p className="sr-only">Loading negotiation</p>
      <div aria-hidden="true">
        <span className="skeleton-line skeleton-price" />
        <span className="skeleton-line" />
        <span className="skeleton-line skeleton-short" />
      </div>
    </div>
  );
}

export function ErrorNotice({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="notice notice-error" role="alert">
      <h2>{title}</h2>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptySoon() {
  return (
    <section className="soon" aria-labelledby="soon-title">
      <h2 id="soon-title">Listings coming soon</h2>
      <p>
        New bikes, computers, and furniture for the Bay Area will show up here after they are
        priced and checked.
      </p>
      <ul className="soon-slots" aria-hidden="true">
        <li />
        <li />
        <li />
        <li />
      </ul>
    </section>
  );
}

export function EmptyCategory({ label }: { label: string }) {
  return (
    <section className="soon" aria-labelledby="empty-category-title">
      <h2 id="empty-category-title">No {label.toLowerCase()} on the board yet</h2>
      <p>Listings in this category will show up here after they are priced and checked.</p>
    </section>
  );
}

export function EmptySearch({ query, category }: { query: string; category?: string }) {
  return (
    <section className="soon" aria-labelledby="empty-search-title">
      <h2 id="empty-search-title">Nothing matches that search</h2>
      <p>
        No listings for “{query}”
        {category ? ` in ${category.toLowerCase()}` : ""}.
      </p>
    </section>
  );
}

export function Missing({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="soon">
      <h1>{title}</h1>
      {children}
    </section>
  );
}
