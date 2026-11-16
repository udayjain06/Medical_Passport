"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "@/lib/api";

export function ResetPasswordForm({ token }: { token: string | null }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    if (!token) {
      setError("This reset link is missing its token.");
      return;
    }

    setBusy(true);
    try {
      await apiRequest<{ status: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setComplete(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The reset request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="reset-title">
      <p className="eyebrow">Medical Passport</p>
      <h1 id="reset-title">Choose a new password</h1>
      {complete ? (
        <>
          <p className="form-success" role="status">Your password was changed. Sign in with the new password.</p>
          <Link className="button" href="/login">Continue to login</Link>
        </>
      ) : (
        <form className="form-grid" method="post" onSubmit={submit}>
          <p>Use at least 12 characters. This reset link expires after 30 minutes.</p>
          {!token && <p className="form-error" role="alert">This reset link is missing its token.</p>}
          <div className="field">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              id="confirm-password"
              name="password_confirmation"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button" type="submit" disabled={!token || busy}>
            {busy ? "Saving…" : "Change password"}
          </button>
        </form>
      )}
      {!complete && <p className="form-footnote"><Link href="/login">Return to login</Link></p>}
    </section>
  );
}
