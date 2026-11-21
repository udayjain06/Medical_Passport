"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/language";

export default function AccountData() {
  const router = useRouter();
  const { t } = useLanguage();
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [consents, setConsents] = useState<Array<{ id: string; purpose: string; version: string; granted_at: string; withdrawn_at: string | null }>>([]);
  const [audit, setAudit] = useState<Array<{ time: string; action: string }>>([]);
  const [loading, setLoading] = useState(true);

  async function loadPrivacyData() {
    try {
      const [records, events] = await Promise.all([
        apiRequest<typeof consents>("/privacy/consents"),
        apiRequest<typeof audit>("/privacy/audit"),
      ]);
      setConsents(records);
      setAudit(events);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load privacy data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([apiRequest<typeof consents>("/privacy/consents"), apiRequest<typeof audit>("/privacy/audit")])
      .then(([records, events]) => {
        if (active) {
          setConsents(records);
          setAudit(events);
        }
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof ApiError ? caught.message : "Could not load privacy data.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function withdrawEmergencyConsent() {
    setBusy(true);
    setError("");
    try {
      await apiRequest("/privacy/consents/emergency_sharing/withdraw", { method: "POST" });
      await loadPrivacyData();
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

  async function exportFhir() {
    setBusy(true);
    setError("");
    try {
      const data = await apiRequest<unknown>("/export/fhir");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/fhir+json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "medical-passport-fhir-r4-aligned.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "FHIR export failed. Try again.");
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
        <p className="eyebrow">{t("Your data, your control")}</p>
        <h1>{t("Data & privacy")}</h1>
        <p>Download a copy of your records or permanently erase your account.</p>
      </header>
      <section className="panel">
        <h2>{t("My consents")}</h2>
        <p>Terms and privacy consent cannot be withdrawn here. Delete your account to stop using the service and erase its account data.</p>
        {loading ? <p role="status">Loading consents…</p> : consents.length === 0 ? <p>No consent records are available.</p> : <ul>{consents.map((consent) => <li key={consent.id}>{consent.purpose.replaceAll("_", " ")} · version {consent.version} · {consent.withdrawn_at ? "withdrawn" : "active"}{consent.purpose === "emergency_sharing" && !consent.withdrawn_at && <button className="text-button" type="button" disabled={busy} onClick={() => void withdrawEmergencyConsent()}>Withdraw and revoke links</button>}</li>)}</ul>}
      </section>
      <section className="panel" style={{ marginTop: 20 }}>
        <h2>{t("FHIR R4-aligned export")}</h2>
        <p>Downloads patient-confirmed, non-conflicted timeline events in a FHIR R4-aligned Bundle. This does not claim ABDM or NHCX compliance.</p>
        <button className="button button-secondary" disabled={busy} onClick={() => void exportFhir()}>{t("Download FHIR export")}</button>
      </section>
      <section className="panel" style={{ marginTop: 20 }}>
        <h2>Account activity</h2>
        <p>Recent account events. This view contains no event payloads.</p>
        {loading ? <p role="status">Loading activity…</p> : audit.length === 0 ? <p>No account activity recorded yet.</p> : <ul>{audit.map((event, index) => <li key={`${event.time}-${index}`}>{new Date(event.time).toLocaleString()} · {event.action}</li>)}</ul>}
      </section>
      <section className="panel">
        <h2>{t("Export my data")}</h2>
        <p>A JSON file with your profile, timeline, document list and emergency links. Document files are not included.</p>
        <button className="button" disabled={busy} onClick={() => void exportData()}>Download export</button>
      </section>
      <section className="panel" style={{ marginTop: 20 }}>
        <h2>{t("Delete my account")}</h2>
        <p>This permanently erases your account, profiles you own, uploaded documents, timeline and emergency links. It cannot be undone.</p>
        <div className="field">
          <label htmlFor="del-pass">Password</label>
          <input id="del-pass" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="del-confirm">Type DELETE to confirm</label>
          <input id="del-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-danger" disabled={busy || !password || confirmText !== "DELETE"} onClick={() => void deleteAccount()}>
          Delete account permanently
        </button>
      </section>
    </main>
  );
}
