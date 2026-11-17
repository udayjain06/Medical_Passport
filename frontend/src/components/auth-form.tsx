"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useState, useSyncExternalStore } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { LanguageSwitcher, useLanguage } from "@/lib/i18n";

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
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAcknowledged, setPrivacyAcknowledged] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { language, t } = useLanguage();
  const hydrated = useSyncExternalStore(subscribeToHydration, getHydratedSnapshot, getServerHydrationSnapshot);
  const signup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await apiRequest<{ user: User }>(`/auth/${signup ? "register" : "login"}`, {
        method: "POST",
        body: JSON.stringify(
          signup
            ? {
                full_name: fullName,
                email,
                password,
                terms_accepted: termsAccepted,
                privacy_acknowledged: privacyAcknowledged,
              }
            : { email, password },
        ),
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
        <LanguageSwitcher />
        <h1 id="form-title">{signup ? t("signupTitle") : t("loginTitle")}</h1>
        <p>{signup ? t("signupIntro") : t("loginIntro")}</p>
        <form className="form-grid" method="post" onSubmit={submit}>
          {signup && <div className="field"><label htmlFor="full-name">{t("fullName")}</label><input id="full-name" name="full_name" autoComplete="name" required maxLength={120} value={fullName} onChange={(event) => setFullName(event.target.value)} /></div>}
          <div className="field"><label htmlFor="email">{t("emailAddress")}</label><input id="email" name="email" type="email" autoComplete="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} /></div>
          <div className="field"><label htmlFor="password">{t("password")}</label><input id="password" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} required minLength={signup ? 12 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{signup && <span className="field-hint">{t("passwordHint")}</span>}</div>
          {signup && <div className="signup-consents">
            <label className="signup-consent" htmlFor="terms-accepted">
              <input id="terms-accepted" name="terms_accepted" type="checkbox" required checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} />
              <span>{language === "hi" ? "मैं सेवा की " : "I agree to the "}<Link href="/terms">{t("terms")}</Link>{language === "hi" ? " से सहमत हूँ।" : "."}</span>
            </label>
            <label className="signup-consent" htmlFor="privacy-acknowledged">
              <input id="privacy-acknowledged" name="privacy_acknowledged" type="checkbox" required checked={privacyAcknowledged} onChange={(event) => setPrivacyAcknowledged(event.target.checked)} />
              <span>{language === "hi" ? "मैं " : "I acknowledge the "}<Link href="/privacy">{t("privacyNotice")}</Link>{language === "hi" ? " को स्वीकार करता/करती हूँ।" : "."}</span>
            </label>
          </div>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button" type="submit" disabled={!hydrated || busy}>{busy ? t("wait") : signup ? t("createAccount") : t("login")}</button>
        </form>
        {!signup && <p className="form-footnote"><Link href="/forgot-password">{t("forgotPassword")}</Link></p>}
        <p className="form-footnote"><Link href={signup ? "/login" : "/signup"}>{signup ? t("loginLink") : t("signupLink")}</Link></p>
      </section>
    </main>
  );
}
