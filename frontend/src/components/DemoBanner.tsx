import { useState } from "react";
import { ApiError, login } from "../api/client";
import { useAuth } from "../auth";

export const DEMO_EMAIL = "demo@fairlot.app";
export const DEMO_PASSWORD = "fairlot-demo";

export function DemoBanner() {
  const { user, refresh } = useAuth();
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  if (user) return null;

  async function enter() {
    setWorking(true);
    setError("");
    try {
      await login(DEMO_EMAIL, DEMO_PASSWORD);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Demo login failed.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <aside className="demo-banner" aria-label="Demo account">
      <div>
        <strong>Judges: try it with the demo account</strong>
        <p>
          Email <code>{DEMO_EMAIL}</code> · Password <code>{DEMO_PASSWORD}</code>. It owns the lounge set
          listing, which already has an offer waiting in Deals.
        </p>
        {error ? <p className="form-error">{error}</p> : null}
      </div>
      <button type="button" className="button-primary" onClick={() => void enter()} disabled={working}>
        {working ? "Logging in…" : "Log in as demo"}
      </button>
    </aside>
  );
}
