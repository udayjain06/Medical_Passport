"use client";

import { useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";

export function EmailVerificationBanner({ verified }: { verified: boolean }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  if (verified) return null;

  async function resend() {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const result = await apiRequest<{ message: string }>("/auth/resend-verification", {
        method: "POST",
      });
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not request another email.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="verification-banner" aria-labelledby="verification-title">
      <div>
        <h2 id="verification-title">Verify your email</h2>
        <p>Emergency links and family sharing stay locked until you verify your address.</p>
        {message && <p className="form-success" role="status">{message}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <button className="button button-secondary" type="button" onClick={resend} disabled={busy}>
        {busy ? "Sending…" : "Resend verification email"}
      </button>
    </section>
  );
}
