import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./auth";
import { Header } from "./components/Header";
import { scrollToTop, startSmoothScroll, stopSmoothScroll, useReducedMotion } from "./lib/scroll";
import { BoardPage } from "./pages/BoardPage";
import { DealsPage } from "./pages/DealsPage";
import { BotsPage } from "./pages/BotsPage";
import { ListingPage } from "./pages/ListingPage";
import { LoginPage } from "./pages/LoginPage";
import { NegotiationPage } from "./pages/NegotiationPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SellPage } from "./pages/SellPage";
import { SignupPage } from "./pages/SignupPage";
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
      <AuthProvider>
      <ScrollReset />
      <Header />
      <main id="content" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<BoardPage />} />
          <Route path="/listings/:id" element={<ListingPage />} />
          <Route path="/negotiations/:id" element={<NegotiationPage />} />
          <Route path="/sell" element={<SellPage />} />
          <Route path="/wants/:id" element={<WantPage />} />
          <Route path="/bots" element={<BotsPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/deals/:threadId" element={<DealsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      </AuthProvider>
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
