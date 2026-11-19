import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate, useSearchParams } from "react-router-dom";
import { boardHref, CATEGORIES, CATEGORY_LABEL, parseCategory, parseSort } from "../lib/format";

export function Header() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const headerRef = useRef<HTMLElement>(null);
  const q = params.get("q")?.trim() ?? "";
  const category = parseCategory(params.get("category"));
  const sort = parseSort(params.get("sort"));
  const [draft, setDraft] = useState(q);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    setDraft(q);
  }, [q]);

  useEffect(() => {
    const onScroll = () => setCompact(window.scrollY > 64);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const node = headerRef.current;
    if (!node) return;
    const apply = () => {
      document.documentElement.style.setProperty("--header-offset", `${node.offsetHeight}px`);
    };
    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(node);
    return () => observer.disconnect();
  }, [compact]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const nextQuery = String(data.get("q") ?? "");
    const nextCategory = parseCategory(String(data.get("category") ?? ""));
    const nextSort = parseSort(String(data.get("sort") ?? ""));
    navigate(boardHref({ q: nextQuery, category: nextCategory, sort: nextSort }));
  }

  return (
    <header
      className={compact ? "masthead masthead-compact" : "masthead"}
      id="site-header"
      ref={headerRef}
      data-compact={compact ? "true" : "false"}
    >
      <div className="wrap masthead-bar">
        <Link className="wordmark" to="/" aria-label="Fairlot, home">
          Fairlot
        </Link>
        <nav className="cats" id="category-nav" aria-label="Categories">
          <Link
            id="category-all"
            to={boardHref({ q, sort })}
            aria-current={category ? undefined : "true"}
          >
            All
          </Link>
          {CATEGORIES.map((item) => (
            <Link
              key={item}
              id={`category-${item}`}
              to={boardHref({ q, category: item, sort })}
              aria-current={category === item ? "true" : undefined}
            >
              {CATEGORY_LABEL[item]}
            </Link>
          ))}
        </nav>
        <NavLink id="add-listing" className="add-listing" to="/sell">
          Add a listing
        </NavLink>
      </div>
      <div className="wrap">
        <form id="lot-search" className="lot-search" role="search" method="get" action="/" onSubmit={onSubmit}>
          <label htmlFor="search-query" className={compact ? "sr-only" : undefined}>
            What do you want?
          </label>
          <div className="search-row">
            <input
              id="search-query"
              name="q"
              type="search"
              enterKeyHint="search"
              placeholder="Road bike under $400 in San Francisco"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              autoComplete="off"
            />
            {category ? <input type="hidden" name="category" value={category} /> : null}
            {sort !== "newest" ? <input type="hidden" name="sort" value={sort} /> : null}
            <button type="submit" data-action="search">
              Search
            </button>
          </div>
        </form>
      </div>
    </header>
  );
}
