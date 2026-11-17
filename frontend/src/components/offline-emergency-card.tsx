"use client";

import { useEffect, useState, type FormEvent } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type EmergencyContact = {
  full_name: string;
  phone_number: string;
  relationship_label: string | null;
};

type Profile = {
  id: string;
  full_name: string;
  blood_group: string | null;
  known_allergies: string | null;
  major_conditions: string | null;
  current_medications: string | null;
  emergency_contacts: EmergencyContact[];
};

type OfflineFields =
  | "full_name"
  | "blood_group"
  | "known_allergies"
  | "major_conditions"
  | "current_medications"
  | "emergency_contacts";

type Card = {
  fields: OfflineFields[];
  lastSyncedAt: string;
  full_name?: string;
  blood_group?: string | null;
  known_allergies?: string | null;
  major_conditions?: string | null;
  current_medications?: string | null;
  emergency_contacts?: Array<Pick<EmergencyContact, "full_name" | "phone_number" | "relationship_label">>;
};

type OfflineMetadata = { fields: OfflineFields[]; lastSyncedAt: string } | null;
type OfflineCardApi = {
  metadata(profileId: string): Promise<OfflineMetadata>;
  save(profileId: string, card: Card, pin: string): Promise<void>;
  remove(profileId: string): Promise<void>;
};

declare global {
  interface Window {
    MedicalPassportOfflineCard?: OfflineCardApi;
  }
}

const FIELD_KEYS: OfflineFields[] = [
  "full_name",
  "blood_group",
  "known_allergies",
  "major_conditions",
  "current_medications",
  "emergency_contacts",
];

let helperScript: Promise<OfflineCardApi> | null = null;

function getOfflineCardApi(): Promise<OfflineCardApi> {
  if (window.MedicalPassportOfflineCard) {
    return Promise.resolve(window.MedicalPassportOfflineCard);
  }
  if (!helperScript) {
    helperScript = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "/offline-card-crypto.js";
      script.async = true;
      script.onload = () => {
        if (window.MedicalPassportOfflineCard) resolve(window.MedicalPassportOfflineCard);
        else reject(new Error("Offline card storage is unavailable."));
      };
      script.onerror = () => reject(new Error("Offline card storage could not be loaded."));
      document.head.appendChild(script);
    });
  }
  return helperScript;
}

export function OfflineEmergencyCard() {
  const { language, t } = useLanguage();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [selected, setSelected] = useState<OfflineFields[]>([]);
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [metadata, setMetadata] = useState<OfflineMetadata>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest<Profile>("/profile")
      .then(async (currentProfile) => {
        const api = await getOfflineCardApi();
        const savedCard = await api.metadata(currentProfile.id);
        if (active) {
          setProfile(currentProfile);
          setMetadata(savedCard);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof ApiError ? caught.message : t("offlineCardLoadError"));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [t]);

  const fieldLabel = (field: OfflineFields) => {
    const labels: Record<OfflineFields, string> = {
      full_name: t("fieldPatientName"),
      blood_group: t("bloodGroup"),
      known_allergies: t("knownAllergies"),
      major_conditions: t("criticalConditions"),
      current_medications: t("currentMedications"),
      emergency_contacts: t("emergencyContacts"),
    };
    return labels[field];
  };

  function toggleField(field: OfflineFields, checked: boolean) {
    setSelected((current) => checked
      ? [...current, field]
      : current.filter((item) => item !== field));
  }

  async function saveCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!profile || selected.length === 0) return;
    if (!/^\d{8,64}$/.test(pin)) {
      setError(t("offlineCardPinHint"));
      return;
    }
    if (pin !== confirmPin) {
      setError(t("offlineCardPinMismatch"));
      return;
    }
    if (!acknowledged) {
      setError(t("offlineCardAcknowledgeError"));
      return;
    }

    setBusy(true);
    try {
      const card: Card = { fields: selected, lastSyncedAt: new Date().toISOString() };
      if (selected.includes("full_name")) card.full_name = profile.full_name;
      if (selected.includes("blood_group")) card.blood_group = profile.blood_group;
      if (selected.includes("known_allergies")) card.known_allergies = profile.known_allergies;
      if (selected.includes("major_conditions")) card.major_conditions = profile.major_conditions;
      if (selected.includes("current_medications")) card.current_medications = profile.current_medications;
      if (selected.includes("emergency_contacts")) {
        card.emergency_contacts = profile.emergency_contacts.map((contact) => ({
          full_name: contact.full_name,
          phone_number: contact.phone_number,
          relationship_label: contact.relationship_label,
        }));
      }

      const offlineCard = await getOfflineCardApi();
      await offlineCard.save(profile.id, card, pin);
      setMetadata({ fields: [...selected], lastSyncedAt: card.lastSyncedAt });
      setPin("");
      setConfirmPin("");
      setAcknowledged(false);
      setMessage(t("offlineCardSaved"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("offlineCardSaveError"));
    } finally {
      setBusy(false);
    }
  }

  async function removeCard() {
    if (!profile || !window.confirm(t("offlineCardRemoveConfirm"))) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const offlineCard = await getOfflineCardApi();
      await offlineCard.remove(profile.id);
      setMetadata(null);
      setMessage(t("offlineCardRemoved"));
    } catch {
      setError(t("offlineCardRemoveError"));
    } finally {
      setBusy(false);
    }
  }

  const dateLabel = metadata
    ? new Date(metadata.lastSyncedAt).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")
    : "";

  return (
    <section className="panel offline-card-setup" aria-labelledby="offline-card-heading">
      <h2 id="offline-card-heading">{t("offlineCardTitle")}</h2>
      <p>{t("offlineCardIntro")}</p>
      <div className="offline-card-warning" role="note">
        <strong>{t("offlineCardRiskTitle")}</strong>
        <p>{t("offlineCardRisk")}</p>
      </div>
      {loading ? (
        <p role="status">{t("offlineCardLoading")}</p>
      ) : profile ? (
        <>
          {metadata && (
            <p role="status">
              {t("offlineCardLastSynced")} {dateLabel}
            </p>
          )}
          <form onSubmit={(event) => void saveCard(event)}>
            <fieldset className="offline-field-list">
              <legend>{t("offlineCardChooseFields")}</legend>
              {FIELD_KEYS.map((field) => (
                <label key={field}>
                  <input
                    type="checkbox"
                    checked={selected.includes(field)}
                    onChange={(event) => toggleField(field, event.target.checked)}
                  />
                  {fieldLabel(field)}
                </label>
              ))}
            </fieldset>
            <div className="form-row">
              <div className="field">
                <label htmlFor="offline-card-pin">{t("offlineCardPin")}</label>
                <input
                  id="offline-card-pin"
                  type="password"
                  inputMode="numeric"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={64}
                  value={pin}
                  onChange={(event) => setPin(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="offline-card-confirm-pin">{t("offlineCardConfirmPin")}</label>
                <input
                  id="offline-card-confirm-pin"
                  type="password"
                  inputMode="numeric"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={64}
                  value={confirmPin}
                  onChange={(event) => setConfirmPin(event.target.value)}
                />
              </div>
            </div>
            <label className="consent-line offline-card-acknowledgement">
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(event) => setAcknowledged(event.target.checked)}
              />
              {t("offlineCardAcknowledge")}
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            {message && <p className="form-success" role="status">{message}</p>}
            <div className="review-actions">
              <button className="button" type="submit" disabled={busy || selected.length === 0 || !acknowledged}>
                {busy ? t("working") : t("offlineCardSave")}
              </button>
              {metadata && profile && (
                <a
                  className="button button-secondary"
                  href={`/offline-card.html?profile=${encodeURIComponent(profile.id)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("offlineCardOpen")}
                </a>
              )}
              {metadata && (
                <button className="button button-danger" type="button" disabled={busy} onClick={() => void removeCard()}>
                  {t("offlineCardRemove")}
                </button>
              )}
            </div>
          </form>
        </>
      ) : (
        <p className="form-error" role="alert">{error || t("offlineCardLoadError")}</p>
      )}
    </section>
  );
}
