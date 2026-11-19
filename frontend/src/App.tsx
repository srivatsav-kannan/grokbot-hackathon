import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/Header";
import { scrollToTop, startSmoothScroll, stopSmoothScroll, useReducedMotion } from "./lib/scroll";
import { BoardPage } from "./pages/BoardPage";
import { ListingPage } from "./pages/ListingPage";
import { NegotiationPage } from "./pages/NegotiationPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SellPage } from "./pages/SellPage";
import { WantPage } from "./pages/WantPage";

function ScrollReset() {
  const location = useLocation();
  useEffect(() => {
    scrollToTop();
  }, [location.pathname, location.search]);
  return null;
}

export function App() {
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) {
      stopSmoothScroll();
      return;
    }
    startSmoothScroll();
    return () => stopSmoothScroll();
  }, [reduced]);

  return (
    <>
      <a className="skip" href="#content">
        Skip to content
      </a>
      <ScrollReset />
      <Header />
      <main id="content" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<BoardPage />} />
          <Route path="/listings/:id" element={<ListingPage />} />
          <Route path="/negotiations/:id" element={<NegotiationPage />} />
          <Route path="/sell" element={<SellPage />} />
          <Route path="/wants/:id" element={<WantPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <footer className="site-footer">
        <div className="wrap">
          <p>Fairlot. Bay Area bikes, computers, and furniture.</p>
          <p>
            <a href="/llms.txt">Notes for agents</a>
          </p>
        </div>
      </footer>
    </>
  );
}
