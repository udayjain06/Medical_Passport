"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "@/lib/api";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await apiRequest<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not request a reset email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="forgot-title">
      <p className="eyebrow">Medical Passport</p>
      <h1 id="forgot-title">Reset your password</h1>
      <p>Enter your account email. If it matches an account, reset instructions will be sent.</p>
      <form className="form-grid" method="post" onSubmit={submit}>
        <div className="field">
          <label htmlFor="reset-email">Email address</label>
          <input
            id="reset-email"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={320}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Please wait…" : "Send reset instructions"}
        </button>
      </form>
      <p className="form-footnote"><Link href="/login">Return to login</Link></p>
    </section>
  );
}
