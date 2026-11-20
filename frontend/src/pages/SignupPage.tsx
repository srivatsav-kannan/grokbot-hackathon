import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, signup } from "../api/client";
import { useAuth } from "../auth";
import { useTitle } from "../lib/title";
import { safeNext } from "./LoginPage";

export function SignupPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  useTitle("Create an account");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      await signup(email.trim(), password);
      await refresh();
      navigate(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account.");
      setWorking(false);
    }
  }

  return (
    <div className="wrap board auth-page">
      <h1>Create an account</h1>
      <p className="lede">You need an account to sell, to send a buyer bot, or to accept a deal. Browsing stays open.</p>
      <form className="publish-form" onSubmit={onSubmit}>
        <label htmlFor="signup-email">
          Email
          <input
            id="signup-email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label htmlFor="signup-password">
          Password
          <input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button className="button-primary" type="submit" disabled={working}>
          {working ? "Creating…" : "Create account"}
        </button>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
      </form>
      <p>
        <Link to={`/login?next=${encodeURIComponent(next)}`}>Log in</Link>
      </p>
    </div>
  );
}
