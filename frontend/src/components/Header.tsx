import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { boardHref, parseCategory, parseSort } from "../lib/format";

export function Header() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const headerRef = useRef<HTMLElement>(null);
  const q = params.get("q")?.trim() ?? "";
  const category = parseCategory(params.get("category"));
  const sort = parseSort(params.get("sort"));
  const [draft, setDraft] = useState(q);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    setDraft(q);
  }, [q]);

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
  }, []);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const nextQuery = String(data.get("q") ?? "");
    navigate(boardHref({ q: nextQuery, category, sort }));
  }

  return (
    <header className="masthead" id="site-header" ref={headerRef}>
      <div className="wrap masthead-bar">
        <Link className="wordmark" to="/" aria-label="Fairlot, home">
          Fairlot
        </Link>
        <nav className="site-nav" aria-label="Main">
          <NavLink to="/" end>
            Browse
          </NavLink>
          <NavLink to="/deals">Deals</NavLink>
        </nav>
        <div className="mast-actions">
          <NavLink id="add-listing" className="add-listing" to="/sell">
            Sell
          </NavLink>
          {user ? (
            <div className="account">
              <button
                type="button"
                className="account-button"
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                onClick={() => setMenuOpen((open) => !open)}
              >
                {user.email}
              </button>
              {menuOpen ? (
                <div className="account-menu" role="menu">
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      void logout();
                    }}
                  >
                    Log out
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <Link to="/login">Log in</Link>
          )}
        </div>
      </div>
      <div className="wrap">
        <form id="lot-search" className="lot-search" role="search" method="get" action="/" onSubmit={onSubmit}>
          <label htmlFor="search-query">What do you want?</label>
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
            <button type="submit" data-action="search">
              Search
            </button>
          </div>
        </form>
      </div>
    </header>
  );
}
