"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type User = { email: string };
type Contact = { id: string; full_name: string; phone_number: string; relationship_label: string | null };
type Profile = {
  full_name: string;
  blood_group: string | null;
  phone_number: string | null;
  known_allergies: string | null;
  major_conditions: string | null;
  current_medications: string | null;
  emergency_contacts: Contact[];
  verification_status: "patient_reported";
};
type Document = { id: string };
type TimelineEvent = { id: string };
type EmergencyShare = { expires_at: string; revoked: boolean };
type Checklist = {
  profile: boolean;
  document: boolean;
  confirmedFact: boolean;
  emergencyCard: boolean;
};

function shown(value: string | null | undefined): string {
  return value?.trim() ? value : "Not recorded";
}

export default function DashboardPage() {
  const { t } = useLanguage();
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [checklist, setChecklist] = useState<Checklist | null>(null);
  const [checklistLoading, setChecklistLoading] = useState(true);
  const [checklistError, setChecklistError] = useState("");
  const checklistController = useRef<AbortController | null>(null);

  const loadChecklist = useCallback(async (patientProfile: Profile, signal?: AbortSignal) => {
    const requestSignal = signal ?? checklistController.current?.signal;
    setChecklistLoading(true);
    setChecklistError("");
    try {
      const [documents, confirmedFacts, shares] = await Promise.all([
        apiRequest<Document[]>("/documents", { signal: requestSignal }),
        apiRequest<TimelineEvent[]>("/timeline?verification_status=confirmed", { signal: requestSignal }),
        apiRequest<EmergencyShare[]>("/emergency/shares", { signal: requestSignal }),
      ]);
      const hasPatientDetails = Boolean(
        patientProfile.blood_group
          || patientProfile.phone_number
          || patientProfile.known_allergies
          || patientProfile.major_conditions
          || patientProfile.current_medications
          || patientProfile.emergency_contacts.length,
      );
      const hasEmergencyCard = shares.length > 0;
      setChecklist({
        profile: hasPatientDetails,
        document: documents.length > 0,
        confirmedFact: confirmedFacts.length > 0,
        emergencyCard: hasEmergencyCard,
      });
    } catch (caught) {
      if (!requestSignal?.aborted) {
        setChecklistError(caught instanceof ApiError ? caught.message : t("firstRunError"));
      }
    } finally {
      if (!requestSignal?.aborted) setChecklistLoading(false);
    }
  }, [t]);

  useEffect(() => {
    const controller = new AbortController();
    checklistController.current = controller;
    let active = true;
    Promise.all([
      apiRequest<User>("/auth/me", { signal: controller.signal }),
      apiRequest<Profile>("/profile", { signal: controller.signal }),
    ])
      .then(([auth, patientProfile]) => {
        if (!active) return;
        setUser(auth);
        setProfile(patientProfile);
        void loadChecklist(patientProfile, controller.signal);
      })
      .catch((caught: unknown) => {
        if (active && !controller.signal.aborted) {
          setError(caught instanceof ApiError ? caught.message : "Could not load your profile.");
        }
      });
    return () => {
      active = false;
      controller.abort();
      if (checklistController.current === controller) checklistController.current = null;
    };
  }, [loadChecklist]);

  const items = profile && checklist ? [
    { id: "profile", title: t("firstRunProfile"), hint: t("firstRunProfileHint"), done: checklist.profile, href: "/profile", action: t("navProfile") },
    { id: "document", title: t("firstRunUpload"), hint: t("firstRunUploadHint"), done: checklist.document, href: "/documents", action: t("navDocuments") },
    { id: "facts", title: t("firstRunReview"), hint: t("firstRunReviewHint"), done: checklist.confirmedFact, href: "/timeline", action: t("navTimeline") },
    { id: "emergency", title: t("firstRunEmergency"), hint: t("firstRunEmergencyHint"), done: checklist.emergencyCard, href: "/emergency", action: t("navEmergency") },
  ] : [];

  return (
    <main className="page-wrap">
      <section className="welcome-panel panel">
        <p className="eyebrow">Your private health space</p>
        <h1>{profile ? `Welcome, ${profile.full_name}` : "Your health information, in one place."}</h1>
        <p>
          {user ? `Signed in as ${user.email}.` : "Loading your account…"} Review your profile and keep the details you have recorded up to date.
        </p>
      </section>
      {error && <p className="form-error" role="alert">{error}</p>}
      {!profile && !error && <p className="loading" role="status">Loading your profile…</p>}

      {profile && (
        <>
          <section className="panel first-run-panel" aria-labelledby="first-run-heading">
            <h2 id="first-run-heading">{t("firstRunTitle")}</h2>
            <p>{t("firstRunIntro")}</p>
            {checklistLoading && <p role="status">{t("firstRunLoading")}</p>}
            {checklistError && (
              <p className="form-error" role="alert">
                {checklistError} <button className="text-button" type="button" onClick={() => void loadChecklist(profile)}>{t("firstRunRetry")}</button>
              </p>
            )}
            {checklist && (
              <ol className="first-run-list">
                {items.map((item, index) => (
                  <li key={item.id}>
                    <span className={item.done ? "first-run-number is-done" : "first-run-number"} aria-hidden="true">
                      {item.done ? "✓" : index + 1}
                    </span>
                    <div>
                      <h3>{item.title}</h3>
                      <p>{item.hint}</p>
                      <span className={item.done ? "first-run-status is-done" : "first-run-status"}>
                        {item.done ? t("firstRunComplete") : t("firstRunNotStarted")}
                      </span>
                    </div>
                    <Link className="button button-secondary button-small" href={item.href}>{item.action}</Link>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <div className="dashboard-grid" style={{ marginTop: 18 }}>
            <section className="panel" aria-labelledby="profile-summary-heading">
              <div className="dashboard-panel-heading">
                <h2 id="profile-summary-heading">Patient profile</h2>
                <span className="status-pill">Patient-reported</span>
              </div>
              <div className="profile-detail-list">
                <div><span className="detail-label">Blood group</span><span className="detail-value">{shown(profile.blood_group)}</span></div>
                <div><span className="detail-label">Contact number</span><span className="detail-value">{shown(profile.phone_number)}</span></div>
                <div><span className="detail-label">Known allergies</span><span className="detail-value">{shown(profile.known_allergies)}</span></div>
                <div><span className="detail-label">Major conditions</span><span className="detail-value">{shown(profile.major_conditions)}</span></div>
              </div>
              <p className="verification-note">These details were entered by you. They have not been clinically verified. “Not recorded” does not mean none.</p>
              <Link className="panel-link" href="/profile">Review or edit profile <span aria-hidden="true">→</span></Link>
            </section>
            <section className="panel" aria-labelledby="records-heading">
              <h2 id="records-heading">Medical records</h2>
              <div className="empty-state">
                <strong>Your private document vault</strong>
                <p>Upload reports and prescriptions, review extracted text, and confirm events for your timeline.</p>
                <Link className="panel-link" href="/documents">Open document vault <span aria-hidden="true">→</span></Link>
              </div>
            </section>
            <section className="panel" aria-labelledby="contacts-heading">
              <h2 id="contacts-heading">Emergency contacts</h2>
              {profile.emergency_contacts.length ? (
                <div className="profile-detail-list">
                  {profile.emergency_contacts.map((contact) => (
                    <div key={contact.id}>
                      <span className="detail-label">{contact.relationship_label || "Contact"}</span>
                      <span className="detail-value">{contact.full_name}<br />{contact.phone_number}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state"><strong>No contact recorded.</strong><p>Add an emergency contact in your profile if you have one to share.</p></div>
              )}
            </section>
            <section className="panel" aria-labelledby="sharing-heading">
              <h2 id="sharing-heading">Emergency sharing</h2>
              <div className="empty-state">
                <strong>Share only what you choose</strong>
                <p>Create an expiring QR code for selected emergency details.</p>
                <Link className="panel-link" href="/emergency">Manage emergency access <span aria-hidden="true">→</span></Link>
              </div>
            </section>
          </div>
        </>
      )}
    </main>
  );
}
