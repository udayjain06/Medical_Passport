"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";

type Contact = { full_name: string; phone_number: string; relationship_label: string };
type ProfileForm = {
  full_name: string;
  date_of_birth: string;
  blood_group: string;
  phone_number: string;
  known_allergies: string;
  major_conditions: string;
  current_medications: string;
  emergency_contacts: Contact[];
};
type ProfileResponse = Omit<ProfileForm, "date_of_birth" | "blood_group" | "phone_number" | "known_allergies" | "major_conditions" | "current_medications" | "emergency_contacts"> & {
  date_of_birth: string | null;
  blood_group: string | null;
  phone_number: string | null;
  known_allergies: string | null;
  major_conditions: string | null;
  current_medications: string | null;
  emergency_contacts: Array<Contact & { id: string }>;
};

const blankContact: Contact = { full_name: "", phone_number: "", relationship_label: "" };
const blankForm: ProfileForm = {
  full_name: "", date_of_birth: "", blood_group: "", phone_number: "", known_allergies: "",
  major_conditions: "", current_medications: "", emergency_contacts: [blankContact],
};

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileForm>(blankForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    apiRequest<ProfileResponse>("/profile")
      .then((profile) => {
        if (!active) return;
        setForm({
          full_name: profile.full_name ?? "", date_of_birth: profile.date_of_birth ?? "",
          blood_group: profile.blood_group ?? "", phone_number: profile.phone_number ?? "",
          known_allergies: profile.known_allergies ?? "", major_conditions: profile.major_conditions ?? "",
          current_medications: profile.current_medications ?? "",
          emergency_contacts: profile.emergency_contacts.length
            ? [{ ...profile.emergency_contacts[0], relationship_label: profile.emergency_contacts[0].relationship_label ?? "" }]
            : [{ ...blankContact }],
        });
      })
      .catch((caught: unknown) => {
        if (active && !(caught instanceof ApiError && caught.status === 404)) {
          setError(caught instanceof ApiError ? caught.message : "Could not load your profile.");
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  function update<K extends keyof ProfileForm>(key: K, value: ProfileForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const contact = form.emergency_contacts[0];
    if (contact && Boolean(contact.full_name.trim()) !== Boolean(contact.phone_number.trim())) {
      setError("Enter both a contact name and phone number, or leave both blank.");
      return;
    }
    setBusy(true);
    const emergencyContacts = contact?.full_name.trim() && contact.phone_number.trim()
      ? [{ ...contact, full_name: contact.full_name.trim(), phone_number: contact.phone_number.trim(), relationship_label: contact.relationship_label.trim() || null }]
      : [];
    try {
      const saved = await apiRequest<ProfileResponse>("/profile", {
        method: "PUT",
        body: JSON.stringify({
          ...form, date_of_birth: form.date_of_birth || null, blood_group: form.blood_group || null,
          phone_number: form.phone_number.trim() || null, known_allergies: form.known_allergies.trim() || null,
          major_conditions: form.major_conditions.trim() || null, current_medications: form.current_medications.trim() || null,
          emergency_contacts: emergencyContacts,
        }),
      });
      setForm((current) => ({ ...current, full_name: saved.full_name }));
      setSuccess("Profile saved.");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  }

  const contact = form.emergency_contacts[0] ?? blankContact;
  return <main className="page-wrap">
    <div className="page-heading"><p className="eyebrow">Your information</p><h1>Patient profile</h1><p>Keep the information you choose to record up to date. Blank fields mean “not recorded.”</p></div>
    {loading ? <p className="loading" role="status">Loading profile…</p> : <div className="profile-layout">
      <form className="panel profile-form" onSubmit={save}>
        <section className="form-section"><h2>About you</h2><div className="form-grid">
          <div className="field"><label htmlFor="profile-name">Full name</label><input id="profile-name" required maxLength={120} value={form.full_name} onChange={(event) => update("full_name", event.target.value)} /></div>
          <div className="form-row">
            <div className="field"><label htmlFor="date-of-birth">Date of birth</label><input id="date-of-birth" type="date" value={form.date_of_birth} onChange={(event) => update("date_of_birth", event.target.value)} /></div>
            <div className="field"><label htmlFor="blood-group">Blood group</label><select id="blood-group" value={form.blood_group} onChange={(event) => update("blood_group", event.target.value)}><option value="">Not recorded</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((group) => <option key={group} value={group}>{group}</option>)}</select></div>
          </div>
          <div className="field"><label htmlFor="phone-number">Contact number</label><input id="phone-number" type="tel" autoComplete="tel" maxLength={32} placeholder="+91 …" value={form.phone_number} onChange={(event) => update("phone_number", event.target.value)} /></div>
        </div></section>
        <section className="form-section"><h2>Medical information</h2><div className="form-grid">
          <div className="field"><label htmlFor="allergies">Known allergies</label><textarea id="allergies" maxLength={4000} placeholder="Leave blank if this has not been recorded." value={form.known_allergies} onChange={(event) => update("known_allergies", event.target.value)} /><span className="field-hint">A blank value does not mean you have no allergies.</span></div>
          <div className="field"><label htmlFor="conditions">Major medical conditions</label><textarea id="conditions" maxLength={4000} placeholder="Leave blank if this has not been recorded." value={form.major_conditions} onChange={(event) => update("major_conditions", event.target.value)} /></div>
          <div className="field"><label htmlFor="medications">Current medications</label><textarea id="medications" maxLength={4000} placeholder="Enter the instructions as given to you." value={form.current_medications} onChange={(event) => update("current_medications", event.target.value)} /><span className="field-hint">This profile does not change or verify medication instructions.</span></div>
        </div></section>
        <section className="form-section"><h2>Emergency contact</h2><div className="form-grid">
          <div className="field"><label htmlFor="contact-name">Contact name</label><input id="contact-name" autoComplete="off" maxLength={120} value={contact.full_name} onChange={(event) => update("emergency_contacts", [{ ...contact, full_name: event.target.value }])} /></div>
          <div className="form-row">
            <div className="field"><label htmlFor="contact-phone">Contact phone</label><input id="contact-phone" type="tel" maxLength={32} placeholder="+91 …" value={contact.phone_number} onChange={(event) => update("emergency_contacts", [{ ...contact, phone_number: event.target.value }])} /></div>
            <div className="field"><label htmlFor="contact-relationship">Relationship (optional)</label><input id="contact-relationship" maxLength={80} value={contact.relationship_label} onChange={(event) => update("emergency_contacts", [{ ...contact, relationship_label: event.target.value }])} /></div>
          </div>
        </div></section>
        {error && <p className="form-error" role="alert">{error}</p>}{success && <p className="form-success" role="status">{success}</p>}
        <div><button className="button" type="submit" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button></div>
      </form>
      <aside className="panel side-note"><span className="status-pill">Patient-reported</span><h2 style={{ marginTop: 17 }}>You stay in control</h2><p>These details are entered by you and are not clinically verified. Only fill in what you know.</p><p>A blank allergy, condition, or medication field means it has not been recorded here. It does not mean “none.”</p><p>Medical Passport is not a substitute for professional medical advice.</p></aside>
    </div>}
  </main>;
}
