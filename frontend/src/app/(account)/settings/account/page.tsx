"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Consent = { id: string; purpose: string; version: string; granted_at: string; withdrawn_at: string | null };
type AuditItem = { time: string; action: string };

export default function AccountData() {
  const { language, t } = useLanguage();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [consents, setConsents] = useState<Consent[] | null>(null);
  const [audit, setAudit] = useState<AuditItem[] | null>(null);
  const [consentMessage, setConsentMessage] = useState("");
  const consentLabel = (purpose: string) => language === "hi"
    ? ({ terms: "सेवा की शर्तें", privacy: "गोपनीयता सूचना", emergency_sharing: "आपातकालीन साझाकरण" } as Record<string, string>)[purpose] ?? purpose.replaceAll("_", " ")
    : purpose.replaceAll("_", " ");

  const refreshPrivacyRecords = useCallback(() => {
    Promise.all([
      apiRequest<Consent[]>("/auth/consents"),
      apiRequest<AuditItem[]>("/auth/audit-log"),
    ]).then(([nextConsents, nextAudit]) => {
      setConsents(nextConsents);
      setAudit(nextAudit);
    }).catch((caught) => {
      setError(caught instanceof ApiError ? caught.message : "Could not load privacy records.");
      setConsents([]);
      setAudit([]);
    });
  }, []);

  useEffect(() => {
    refreshPrivacyRecords();
  }, [refreshPrivacyRecords]);

  async function withdrawEmergencyConsent() {
    setBusy(true);
    setError("");
    setConsentMessage("");
    try {
      const result = await apiRequest<{ withdrawn_records: number; revoked_links: number }>("/auth/consents/emergency_sharing/withdraw", { method: "POST" });
      setConsentMessage(`Consent withdrawn. ${result.revoked_links} active emergency link(s) revoked.`);
      refreshPrivacyRecords();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not withdraw consent.");
    } finally {
      setBusy(false);
    }
  }

  async function exportData() {
    setBusy(true);
    setError("");
    try {
      const data = await apiRequest<unknown>("/auth/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "medical-passport-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Export failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount() {
    setBusy(true);
    setError("");
    try {
      await apiRequest("/auth/delete-account", { method: "POST", body: JSON.stringify({ password }) });
      router.replace("/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the account.");
      setBusy(false);
    }
  }

  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">{language === "hi" ? "आपका डेटा, आपका नियंत्रण" : "Your data, your control"}</p>
        <h1>{t("dataPrivacyTitle")}</h1>
        <p>{t("dataPrivacyIntro")}</p>
      </header>
      <section className="panel">
        <h2>{t("exportMyData")}</h2>
        <p>{t("exportIntro")}</p>
        <button className="button" disabled={busy} onClick={() => void exportData()}>{t("downloadExport")}</button>
      </section>
      <section className="panel" style={{ marginTop: 20 }} aria-labelledby="consent-heading">
        <h2 id="consent-heading">{t("myConsents")}</h2>
        <p>{t("consentWithdrawInfo")}</p>
        {consents === null ? <p role="status">{t("loadingConsents")}</p> : consents.length === 0 ? <p>{t("noConsents")}</p> : <ul className="privacy-record-list">
          {consents.map((consent) => <li key={consent.id}>
            <span><strong>{consentLabel(consent.purpose)}</strong> · {consent.version} · {new Date(consent.granted_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")}</span>
            <span>{consent.withdrawn_at ? `${t("withdrawn")} ${new Date(consent.withdrawn_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")}` : t("consentActive")}</span>
          </li>)}
        </ul>}
        {consents?.some((consent) => consent.purpose === "emergency_sharing" && !consent.withdrawn_at) && <button className="button button-secondary" disabled={busy} onClick={() => void withdrawEmergencyConsent()}>{t("withdrawEmergency")}</button>}
        {consentMessage && <p role="status">{consentMessage}</p>}
      </section>
      <section className="panel" style={{ marginTop: 20 }} aria-labelledby="audit-heading">
        <h2 id="audit-heading">{t("recentActivity")}</h2>
        <p>{t("activityIntro")}</p>
        {audit === null ? <p role="status">{t("loadingActivity")}</p> : audit.length === 0 ? <p>{t("noActivity")}</p> : <ul className="privacy-record-list">
          {audit.map((item, index) => <li key={`${item.time}-${item.action}-${index}`}><time dateTime={item.time}>{new Date(item.time).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")}</time><span>{item.action.replaceAll(".", " · ")}</span></li>)}
        </ul>}
      </section>
      <section className="panel" style={{ marginTop: 20 }}>
        <h2>{t("deleteAccount")}</h2>
        <p>{t("deleteAccountIntro")}</p>
        <div className="field">
          <label htmlFor="del-pass">{t("password")}</label>
          <input id="del-pass" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="del-confirm">{t("deleteConfirm")}</label>
          <input id="del-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-danger" disabled={busy || !password || confirmText !== "DELETE"} onClick={() => void deleteAccount()}>
          {t("deletePermanently")}
        </button>
      </section>
    </main>
  );
}
