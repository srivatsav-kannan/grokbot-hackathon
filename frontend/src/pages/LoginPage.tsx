import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, login } from "../api/client";
import { useAuth } from "../auth";
import { useTitle } from "../lib/title";
import { DEMO_EMAIL, DEMO_PASSWORD } from "../components/DemoBanner";

export function LoginPage() {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  useTitle("Log in");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setWorking(true);
    setError("");
    try {
      await login(email.trim(), password);
      await refresh();
      navigate(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log in.");
      setWorking(false);
    }
  }

  return (
    <div className="wrap board auth-page">
      <h1>Log in</h1>
      <form className="publish-form" onSubmit={onSubmit}>
        <label htmlFor="login-email">
          Email
          <input
            id="login-email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label htmlFor="login-password">
          Password
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <button className="button-primary" type="submit" disabled={working}>
          {working ? "Signing in…" : "Log in"}
        </button>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
      </form>
      <p>
        <Link to={`/signup?next=${encodeURIComponent(next)}`}>Create an account</Link>
      </p>
    </div>
  );
}

export function safeNext(value: string | null): string {
  if (value && value.startsWith("/") && !value.startsWith("//")) return value;
  return "/";
}
