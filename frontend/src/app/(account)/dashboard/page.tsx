"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";

type User = { email: string };
type Contact = { id: string; full_name: string; phone_number: string; relationship_label: string | null };
type Profile = {
  full_name: string;
  blood_group: string | null;
  phone_number: string | null;
  known_allergies: string | null;
  major_conditions: string | null;
  emergency_contacts: Contact[];
  verification_status: "patient_reported";
};

function shown(value: string | null | undefined): string {
  return value?.trim() ? value : "Not recorded";
}

export default function DashboardPage() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([apiRequest<User>("/auth/me"), apiRequest<Profile>("/profile")])
      .then(([auth, patientProfile]) => {
        if (active) {
          setUser(auth);
          setProfile(patientProfile);
        }
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof ApiError ? caught.message : "Could not load your profile.");
      });
    return () => { active = false; };
  }, []);

  return <main className="page-wrap">
    <section className="welcome-panel panel">
      <p className="eyebrow">Your private health space</p>
      <h1>{profile ? `Welcome, ${profile.full_name}` : "Your health information, in one place."}</h1>
      <p>{user ? `Signed in as ${user.email}.` : "Loading your account…"} Review your profile and keep the details you have recorded up to date.</p>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    {!profile && !error && <p className="loading" role="status">Loading your profile…</p>}
    {profile && <div className="dashboard-grid" style={{ marginTop: 18 }}>
      <section className="panel" aria-labelledby="profile-summary-heading">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}><h2 id="profile-summary-heading">Patient profile</h2><span className="status-pill">Patient-reported</span></div>
        <div className="profile-detail-list">
          <div><span className="detail-label">Blood group</span><span className="detail-value">{shown(profile.blood_group)}</span></div>
          <div><span className="detail-label">Contact number</span><span className="detail-value">{shown(profile.phone_number)}</span></div>
          <div><span className="detail-label">Known allergies</span><span className="detail-value">{shown(profile.known_allergies)}</span></div>
          <div><span className="detail-label">Major conditions</span><span className="detail-value">{shown(profile.major_conditions)}</span></div>
        </div>
        <p className="verification-note">These details were entered by you. They have not been clinically verified. “Not recorded” does not mean none.</p>
        <Link className="panel-link" href="/profile">Review or edit profile <span aria-hidden="true">→</span></Link>
      </section>
      <section className="panel" aria-labelledby="records-heading"><h2 id="records-heading">Medical records</h2><div className="empty-state"><strong>Your private document vault</strong><p>Upload reports and prescriptions, review extracted text, and confirm events for your timeline.</p><Link className="panel-link" href="/documents">Open document vault →</Link></div></section>
      <section className="panel" aria-labelledby="contacts-heading">
        <h2 id="contacts-heading">Emergency contacts</h2>
        {profile.emergency_contacts.length ? <div className="profile-detail-list">{profile.emergency_contacts.map((contact) => <div key={contact.id}><span className="detail-label">{contact.relationship_label || "Contact"}</span><span className="detail-value">{contact.full_name}<br />{contact.phone_number}</span></div>)}</div> : <div className="empty-state"><strong>No contact recorded.</strong><p>Add an emergency contact in your profile if you have one to share.</p></div>}
      </section>
      <section className="panel" aria-labelledby="sharing-heading"><h2 id="sharing-heading">Emergency sharing</h2><div className="empty-state"><strong>Share only what you choose</strong><p>Create an expiring QR code for selected emergency details.</p><Link className="panel-link" href="/emergency">Manage emergency access →</Link></div></section>
    </div>}
  </main>;
}
