"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useState, useSyncExternalStore } from "react";
import { apiRequest, ApiError } from "@/lib/api";

type Props = { mode: "login" | "signup" };
type User = { id: string; email: string };
const subscribeToHydration = (callback: () => void) => {
  const timer = window.setTimeout(callback, 0);
  return () => window.clearTimeout(timer);
};
const getHydratedSnapshot = () => true;
const getServerHydrationSnapshot = () => false;

export function AuthForm({ mode }: Props) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const hydrated = useSyncExternalStore(subscribeToHydration, getHydratedSnapshot, getServerHydrationSnapshot);
  const signup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest<{ user: User }>(`/auth/${signup ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify(signup ? { full_name: fullName, email, password } : { email, password }),
      });
      router.replace("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-wrap">
      <section className="auth-card" aria-labelledby="form-title">
        <p className="eyebrow">Medical Passport</p>
        <h1 id="form-title">{signup ? "Create your account" : "Welcome back"}</h1>
        <p>{signup ? "Begin with a private, patient-reported health profile." : "Log in to continue to your health profile."}</p>
        <form className="form-grid" method="post" onSubmit={submit}>
          {signup && <div className="field"><label htmlFor="full-name">Full name</label><input id="full-name" name="full_name" autoComplete="name" required maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} /></div>}
          <div className="field"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} /></div>
          <div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} required minLength={signup ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{signup && <span className="field-hint">Use at least 12 characters.</span>}</div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button" type="submit" disabled={!hydrated || busy}>{busy ? "Please wait…" : signup ? "Create account" : "Log in"}</button>
        </form>
        <p className="form-footnote">{signup ? "Already registered? " : "New to Medical Passport? "}<Link href={signup ? "/login" : "/signup"}>{signup ? "Log in" : "Create an account"}</Link></p>
      </section>
    </main>
  );
}
