"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";
import { OfflineEmergencyCard } from "@/components/offline-emergency-card";

const FIELDS = ["full_name", "blood_group", "known_allergies", "major_conditions", "current_medications", "emergency_contacts"] as const;
const EXPIRY_OPTIONS = [
  { hours: 1, label: "1 hour" },
  { hours: 24, label: "24 hours" },
  { hours: 168, label: "7 days" },
  { hours: 720, label: "30 days" },
  { hours: 8760, label: "1 year (wallet card)" },
];

type Share = {
  id: string;
  expires_at: string;
  revoked: boolean;
  fields: string[];
  created_at: string;
  label: string | null;
  access_count: number;
  last_accessed_at: string | null;
};
type Created = { id: string; url: string; qr_png_data_url: string; expires_at: string; label: string | null; patient_name: string };
type AccessEntry = { accessed_at: string; ip_prefix: string | null; user_agent: string | null };

function WalletCard({ card }: { card: Created }) {
  const { language, t } = useLanguage();
  return (
    <div className="wallet-card" aria-hidden="true">
      <p className="wallet-title">{t("emergencyWalletTitle")}</p>
      <Image unoptimized width={180} height={180} src={card.qr_png_data_url} alt="" />
      <p className="wallet-name">{card.patient_name}</p>
      <p className="wallet-hint">{t("scanForEmergency")}</p>
      <p className="wallet-hint">{t("validUntil")} {new Date(card.expires_at).toLocaleDateString(language === "hi" ? "hi-IN" : "en-IN")}</p>
    </div>
  );
}

export default function Emergency() {
  const { language, t } = useLanguage();
  const labelFor = (field: string) => {
    if (language === "hi") return ({
      full_name: t("fieldPatientName"), blood_group: t("bloodGroup"), known_allergies: t("knownAllergies"),
      major_conditions: t("criticalConditions"), current_medications: t("currentMedications"), emergency_contacts: t("emergencyContacts"),
    } as Record<string, string>)[field] ?? field;
    return ({ full_name: "Patient name", blood_group: "Blood group", known_allergies: "Known allergies", major_conditions: "Critical conditions", current_medications: "Current medications", emergency_contacts: "Emergency contacts" } as Record<string, string>)[field] ?? field;
  };
  const [selected, setSelected] = useState<string[]>(["full_name", "blood_group", "known_allergies", "major_conditions", "emergency_contacts"]);
  const [hours, setHours] = useState(24);
  const [label, setLabel] = useState("");
  const [consent, setConsent] = useState(false);
  const [shares, setShares] = useState<Share[]>([]);
  const [created, setCreated] = useState<Created | null>(null);
  const [logs, setLogs] = useState<Record<string, AccessEntry[]>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setShares(await apiRequest<Share[]>("/emergency/shares"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load links");
    }
  }, []);

  useEffect(() => {
    apiRequest<Share[]>("/emergency/shares")
      .then(setShares)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load links"));
  }, []);

  async function guarded(task: () => Promise<void>, fallback: string) {
    setBusy(true);
    setError("");
    try {
      await task();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  const create = () =>
    guarded(async () => {
      setCreated(
        await apiRequest<Created>("/emergency/shares", {
          method: "POST",
          body: JSON.stringify({ fields: selected, expires_in_hours: hours, consent, label: label.trim() || null }),
        }),
      );
      setConsent(false);
    }, "Could not create link");

  const revoke = (id: string) =>
    guarded(async () => {
      await apiRequest(`/emergency/shares/${id}`, { method: "DELETE" });
      if (created?.id === id) setCreated(null);
    }, "Could not revoke link");

  const renew = (id: string) => {
    const confirmMessage = language === "hi"
      ? "यह पुराना QR बदल देगा (पुराने कार्ड काम नहीं करेंगे)। नया लिंक रखने वाला व्यक्ति चुने गए वही क्षेत्र एक वर्ष तक देख सकता है। जारी रखें?"
      : "This replaces the old QR with a new one (old cards stop working). Anyone with the new link can view the same selected fields for a year. Continue?";
    if (!window.confirm(confirmMessage)) return;
    return guarded(async () => {
      setCreated(
        await apiRequest<Created>(`/emergency/shares/${id}/renew`, {
          method: "POST",
          body: JSON.stringify({ expires_in_hours: 8760, consent: true }),
        }),
      );
    }, "Could not renew link");
  };

  const toggleLog = (id: string) =>
    guarded(async () => {
      if (logs[id]) {
        setLogs((current) => {
          const next = { ...current };
          delete next[id];
          return next;
        });
        return;
      }
      const entries = await apiRequest<AccessEntry[]>(`/emergency/shares/${id}/access-log`);
      setLogs((current) => ({ ...current, [id]: entries }));
    }, "Could not load access history");

  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">{t("emergencyEyebrow")}</p>
        <h1>{t("emergencyTitle")}</h1>
        <p>{t("emergencyIntro")}</p>
      </header>

      <section className="panel">
        <h2>{t("chooseInformation")}</h2>
        <div className="emergency-fields">
          {FIELDS.map((f) => (
            <label key={f}>
              <input
                type="checkbox"
                checked={selected.includes(f)}
                onChange={(e) => setSelected((v) => (e.target.checked ? [...v, f] : v.filter((x) => x !== f)))}
              />
              {labelFor(f)}
            </label>
          ))}
        </div>
        <p className="field-hint">
          {t("confirmedRecordsHint")}
        </p>
        <div className="form-row">
          <div className="field">
            <label htmlFor="share-expiry">{t("linkExpires")}</label>
            <select id="share-expiry" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
              {EXPIRY_OPTIONS.map((o) => (
                <option key={o.hours} value={o.hours}>{language === "hi" ? ({ 1: "1 घंटा", 24: "24 घंटे", 168: "7 दिन", 720: "30 दिन", 8760: "1 वर्ष (वॉलेट कार्ड)" } as Record<number, string>)[o.hours] : o.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="share-label">{t("optionalLabel")}</label>
            <input id="share-label" maxLength={80} value={label} placeholder={t("walletCard")} onChange={(e) => setLabel(e.target.value)} />
          </div>
        </div>
        <label className="consent-line">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          {t("shareConsent")}
        </label>
        <button className="button" disabled={busy || !consent || selected.length === 0} onClick={() => void create()}>
          {busy ? t("working") : t("createEmergencyQr")}
        </button>
        {error && <p className="form-error" role="alert">{error}</p>}
        {created && (
          <div className="qr-result">
            <Image unoptimized width={220} height={220} src={created.qr_png_data_url} alt="Emergency access QR code" />
            <p><a href={created.url}>{created.url}</a></p>
            <p className="field-hint">{t("savePrintNote")}</p>
            <div className="review-actions" style={{ justifyContent: "center" }}>
              <a className="button button-secondary" download="medical-passport-emergency-qr.png" href={created.qr_png_data_url}>{t("downloadQr")}</a>
              <button className="button" type="button" onClick={() => window.print()}>{t("printWalletCard")}</button>
            </div>
          </div>
        )}
      </section>

      <OfflineEmergencyCard />

      <section className="panel share-list">
        <h2>{t("activePreviousLinks")}</h2>
        {shares.length === 0 ? (
          <p>{t("noEmergencyLinks")}</p>
        ) : (
          shares.map((s) => {
            const active = !s.revoked && new Date(s.expires_at) > new Date();
            return (
              <div key={s.id}>
                <div className="share-row">
                  <span>
                    <strong>{s.label ?? t("emergencyLink")}</strong> · {s.fields.map(labelFor).join(", ")}
                    <br />
                    {s.revoked ? t("revoked") : active ? t("active") : t("expired")} · {t("expires")} {new Date(s.expires_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")} ·
                    {t("viewed")} {s.access_count}×{s.last_accessed_at ? `, ${t("last")} ${new Date(s.last_accessed_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")}` : ""}
                  </span>
                  <span className="review-actions">
                    {s.access_count > 0 && (
                      <button className="button button-small button-secondary" disabled={busy} onClick={() => void toggleLog(s.id)}>
                        {logs[s.id] ? t("hideHistory") : t("whoViewed")}
                      </button>
                    )}
                    <button className="button button-small button-secondary" disabled={busy} onClick={() => void renew(s.id)}>{t("renew")}</button>
                    {active && <button className="button button-small button-danger" disabled={busy} onClick={() => void revoke(s.id)}>{t("revoke")}</button>}
                  </span>
                </div>
                {logs[s.id] && (
                  <ul className="access-log">
                    {logs[s.id].map((entry, i) => (
                      <li key={i}>
                        {new Date(entry.accessed_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")} · {t("network")} {entry.ip_prefix ?? t("unknown")} · {entry.user_agent ?? t("unknown")}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </section>
      {created && <WalletCard card={created} />}
    </main>
  );
}
