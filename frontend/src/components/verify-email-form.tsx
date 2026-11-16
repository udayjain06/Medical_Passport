"use client";

import Link from "next/link";
import { useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";

export function VerifyEmailForm({ token }: { token: string | null }) {
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState("");

  async function verify() {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest<{ status: string }>("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      setVerified(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The verification request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="verify-title">
      <p className="eyebrow">Medical Passport</p>
      <h1 id="verify-title">Verify your email</h1>
      {verified ? (
        <>
          <p className="form-success" role="status">Your email is verified. You can continue to your account.</p>
          <Link className="button" href="/dashboard">Continue to Medical Passport</Link>
        </>
      ) : (
        <>
          <p>Confirm this one-time link to verify your email address.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          {!token && <p className="form-error" role="alert">This verification link is missing its token.</p>}
          <button className="button" type="button" onClick={verify} disabled={!token || busy}>
            {busy ? "Verifying…" : "Verify email"}
          </button>
          <p className="form-footnote"><Link href="/login">Return to login</Link></p>
        </>
      )}
    </section>
  );
}
