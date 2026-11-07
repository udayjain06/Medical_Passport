"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";

const FIELDS = ["full_name", "blood_group", "known_allergies", "major_conditions", "current_medications", "emergency_contacts"] as const;
const LABELS: Record<string, string> = {
  full_name: "Patient name",
  blood_group: "Blood group",
  known_allergies: "Known allergies",
  major_conditions: "Critical conditions",
  current_medications: "Current medications",
  emergency_contacts: "Emergency contacts",
};
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
  return (
    <div className="wallet-card" aria-hidden="true">
      <p className="wallet-title">Medical Passport · Emergency</p>
      <Image unoptimized width={180} height={180} src={card.qr_png_data_url} alt="" />
      <p className="wallet-name">{card.patient_name}</p>
      <p className="wallet-hint">Scan for allergies, conditions and emergency contacts · आपातकालीन जानकारी के लिए स्कैन करें</p>
      <p className="wallet-hint">Valid until {new Date(card.expires_at).toLocaleDateString()}</p>
    </div>
  );
}

export default function Emergency() {
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
    if (!window.confirm("This replaces the old QR with a new one (old cards stop working). Anyone with the new link can view the same selected fields for a year. Continue?")) return;
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
        <p className="eyebrow">Consent-controlled access</p>
        <h1>Emergency profile</h1>
        <p>
          Choose exactly what someone with your QR link can see. Anyone holding the link can view these fields until
          it expires or you revoke it. Every view is recorded below.
        </p>
      </header>

      <section className="panel">
        <h2>Choose information to share</h2>
        <div className="emergency-fields">
          {FIELDS.map((f) => (
            <label key={f}>
              <input
                type="checkbox"
                checked={selected.includes(f)}
                onChange={(e) => setSelected((v) => (e.target.checked ? [...v, f] : v.filter((x) => x !== f)))}
              />
              {LABELS[f]}
            </label>
          ))}
        </div>
        <p className="field-hint">
          Allergies, conditions and recent prescriptions you have confirmed from uploaded records are included
          automatically (with their dates) when you share those fields.
        </p>
        <div className="form-row">
          <div className="field">
            <label htmlFor="share-expiry">Link expires</label>
            <select id="share-expiry" value={hours} onChange={(e) => setHours(Number(e.target.value))}>
              {EXPIRY_OPTIONS.map((o) => (
                <option key={o.hours} value={o.hours}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="share-label">Label (optional)</label>
            <input id="share-label" maxLength={80} value={label} placeholder="Wallet card, phone lock screen…" onChange={(e) => setLabel(e.target.value)} />
          </div>
        </div>
        <label className="consent-line">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          I understand anyone with this QR link can view the selected information.
        </label>
        <button className="button" disabled={busy || !consent || selected.length === 0} onClick={() => void create()}>
          {busy ? "Working…" : "Create emergency QR"}
        </button>
        {error && <p className="form-error" role="alert">{error}</p>}
        {created && (
          <div className="qr-result">
            <Image unoptimized width={220} height={220} src={created.qr_png_data_url} alt="Emergency access QR code" />
            <p><a href={created.url}>{created.url}</a></p>
            <p className="field-hint">Save or print this now. For security the link cannot be shown again; use Renew to get a fresh QR.</p>
            <div className="review-actions" style={{ justifyContent: "center" }}>
              <a className="button button-secondary" download="medical-passport-emergency-qr.png" href={created.qr_png_data_url}>Download QR</a>
              <button className="button" type="button" onClick={() => window.print()}>Print wallet card</button>
            </div>
          </div>
        )}
      </section>

      <section className="panel share-list">
        <h2>Active and previous links</h2>
        {shares.length === 0 ? (
          <p>No emergency links have been created.</p>
        ) : (
          shares.map((s) => {
            const active = !s.revoked && new Date(s.expires_at) > new Date();
            return (
              <div key={s.id}>
                <div className="share-row">
                  <span>
                    <strong>{s.label ?? "Emergency link"}</strong> · {s.fields.map((f) => LABELS[f]).join(", ")}
                    <br />
                    {s.revoked ? "Revoked" : active ? "Active" : "Expired"} · expires {new Date(s.expires_at).toLocaleString()} ·
                    viewed {s.access_count}×{s.last_accessed_at ? `, last ${new Date(s.last_accessed_at).toLocaleString()}` : ""}
                  </span>
                  <span className="review-actions">
                    {s.access_count > 0 && (
                      <button className="button button-small button-secondary" disabled={busy} onClick={() => void toggleLog(s.id)}>
                        {logs[s.id] ? "Hide history" : "Who viewed"}
                      </button>
                    )}
                    <button className="button button-small button-secondary" disabled={busy} onClick={() => void renew(s.id)}>Renew</button>
                    {active && <button className="button button-small button-danger" disabled={busy} onClick={() => void revoke(s.id)}>Revoke</button>}
                  </span>
                </div>
                {logs[s.id] && (
                  <ul className="access-log">
                    {logs[s.id].map((entry, i) => (
                      <li key={i}>
                        {new Date(entry.accessed_at).toLocaleString()} · network {entry.ip_prefix ?? "unknown"} · {entry.user_agent ?? "unknown device"}
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
