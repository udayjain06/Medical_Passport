"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Section = "overview" | "profile" | "documents" | "timeline" | "family" | "emergency";
type Patient = {
  id: string;
  name: string;
  dob: string;
  blood: string;
  allergies: string;
  conditions: string;
  extractionCandidate: string;
  contact: string;
  relationship: string;
};

const patients: Patient[] = [
  {
    id: "aarav",
    name: "Aarav Mehta",
    dob: "2001-08-14",
    blood: "O+",
    allergies: "Pollen — sneezing and watery eyes",
    conditions: "Seasonal allergic rhinitis; history of migraine",
    extractionCandidate: "Cetirizine 10 mg · as needed · historical consultation",
    contact: "Riya Mehta · fictional contact",
    relationship: "Primary profile",
  },
  {
    id: "ira",
    name: "Ira Mehta",
    dob: "2012-03-22",
    blood: "B+",
    allergies: "No reported allergies",
    conditions: "Mild seasonal asthma · fictional sample",
    extractionCandidate: "Salbutamol inhaler · sample prescription",
    contact: "Aarav Mehta · fictional contact",
    relationship: "Dependent · sample only",
  },
];

const documents = [
  { id: "consult", patientId: "aarav", name: "Consultation summary", date: "12 Feb 2026", detail: "Seasonal allergy review" },
  { id: "cbc", patientId: "aarav", name: "CBC report", date: "05 Feb 2026", detail: "Sample report · fictional values" },
  { id: "rx", patientId: "aarav", name: "Historical prescription", date: "12 Feb 2026", detail: "Cetirizine 10 mg · as needed" },
  { id: "ira-consult", patientId: "ira", name: "Paediatric consultation", date: "03 Mar 2026", detail: "Sample asthma follow-up" },
  { id: "ira-rx", patientId: "ira", name: "Sample prescription", date: "03 Mar 2026", detail: "Salbutamol inhaler · fictional example" },
];

const navigation: { id: Section; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "profile", label: "Patient profile" },
  { id: "documents", label: "Documents & OCR" },
  { id: "timeline", label: "Medical timeline" },
  { id: "family", label: "Family profiles" },
  { id: "emergency", label: "Emergency QR" },
];

const documentText: Record<string, string[]> = {
  consult: ["SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE", "Consultation summary · 12 February 2026", "Patient-reported seasonal allergy symptoms: sneezing and watery eyes during pollen exposure.", "Historical note: migraine reported by patient.", "Sample only. No clinician or laboratory issued this document."],
  cbc: ["SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE", "Complete blood count · 05 February 2026", "Haemoglobin: 14.2 g/dL · WBC: 6.1 × 10⁹/L · Platelets: 245 × 10⁹/L", "These fictional values are for interface demonstration only."],
  rx: ["SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE", "Historical prescription · 12 February 2026", "Cetirizine 10 mg · recorded as needed", "This is a synthetic historical example, not medical advice."],
  "ira-consult": ["SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE", "Paediatric consultation · 03 March 2026", "Sample follow-up note: mild seasonal asthma, as reported by the fictional family.", "This fictional example is for interface demonstration only."],
  "ira-rx": ["SYNTHETIC TEST DOCUMENT — NOT FOR CLINICAL USE", "Sample prescription · 03 March 2026", "Salbutamol inhaler · fictional example", "This is not a real prescription or medical advice."],
};

export default function DemoPage() {
  const [section, setSection] = useState<Section>("overview");
  const [patientId, setPatientId] = useState("aarav");
  const [profile, setProfile] = useState<Record<string, Patient>>(() => Object.fromEntries(patients.map((patient) => [patient.id, patient])));
  const [notice, setNotice] = useState("");
  const [reviewByPatient, setReviewByPatient] = useState<Record<string, "accepted" | "rejected" | undefined>>({});
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [selectedFields, setSelectedFields] = useState(["name", "blood", "allergies"]);
  const [qrShown, setQrShown] = useState(false);
  const activePatient = profile[patientId];
  const activeDocuments = documents.filter((document) => document.patientId === patientId);
  const previewDocument = activeDocuments.find((document) => document.id === previewId);
  const activeReview = reviewByPatient[patientId];

  useEffect(() => {
    if (!previewId) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setPreviewId(null);
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [previewId]);

  function announce(message: string) {
    setNotice(`${message} Simulated only; no data was sent or saved.`);
  }

  function switchPatient(id: string) {
    setPatientId(id);
    setNotice(`Showing ${profile[id].name}'s synthetic profile. Changes remain in this page session.`);
  }

  function updateProfile(field: keyof Patient, value: string) {
    setProfile((current) => ({ ...current, [patientId]: { ...current[patientId], [field]: value } }));
  }

  function toggleField(field: string) {
    setSelectedFields((current) => current.includes(field) ? current.filter((item) => item !== field) : [...current, field]);
    setQrShown(false);
  }

  return (
    <main className="page-wrap demo-workspace">
      <aside className="demo-banner" role="status">DEMO MODE — SYNTHETIC DATA · Fictional information, not for clinical use. Changes stay in this browser session.</aside>
      <header className="page-heading">
        <p className="eyebrow">MEDICAL PASSPORT · INTERACTIVE WALKTHROUGH</p>
        <h1>Welcome, {activePatient.name}</h1>
        <p>Explore the patient passport using fictional sample data. Actions below are demonstrations only.</p>
      </header>

      <nav className="demo-nav" aria-label="Demo sections">
        {navigation.map((item) => (
          <button key={item.id} type="button" aria-current={section === item.id ? "page" : undefined} className={`button ${section === item.id ? "" : "button-secondary"}`} onClick={() => { setSection(item.id); setNotice(""); }}>
            {item.label}
          </button>
        ))}
      </nav>

      {notice && <p className="form-success" role="status">{notice}</p>}

      {section === "overview" && <section className="card-grid">
        <article className="panel"><p className="eyebrow">PATIENT-REPORTED</p><h2>{activePatient.blood} blood group</h2><p>{activePatient.allergies}</p></article>
        <article className="panel"><p className="eyebrow">PASSPORT SUMMARY</p><h2>Health notes</h2><p>{activePatient.conditions}</p></article>
        <article className="panel"><p className="eyebrow">RECORDS</p><h2>{activeDocuments.length} sample documents</h2><button className="button button-secondary" onClick={() => setSection("documents")}>Review documents</button></article>
      </section>}

      {section === "profile" && <section className="panel demo-panel"><h2>Patient profile</h2><p className="demo-disclaimer">Fictional profile · edits only update local React state for this page session.</p>
        <label>Full name<input value={activePatient.name} onChange={(event) => updateProfile("name", event.target.value)}/></label>
        <label>Date of birth<input type="date" value={activePatient.dob} onChange={(event) => updateProfile("dob", event.target.value)}/></label>
        <label>Blood group<input value={activePatient.blood} onChange={(event) => updateProfile("blood", event.target.value)}/></label>
        <label>Known allergies<textarea value={activePatient.allergies} onChange={(event) => updateProfile("allergies", event.target.value)}/></label>
        <label>Conditions<textarea value={activePatient.conditions} onChange={(event) => updateProfile("conditions", event.target.value)}/></label>
        <button className="button" onClick={() => announce("Profile updated.")}>Save profile</button></section>}

      {section === "documents" && <section className="panel demo-panel"><h2>Documents & extraction review · {activePatient.name}</h2><p className="demo-disclaimer">Sample previews and OCR review are simulated. Uploads are not stored or processed.</p>
        <div className="demo-document-list">{activeDocuments.map((document) => <article className="document-card" key={document.id}><div><h3>{document.name} · {document.date}</h3><p>{document.detail}</p></div><button className="button button-secondary" onClick={() => setPreviewId(document.id)}>Preview sample</button></article>)}</div>
        <h3>Extracted candidate · {activeReview ?? "pending review"}</h3><p>{activePatient.extractionCandidate}</p>
        <div className="demo-actions"><button className="button" onClick={() => { setReviewByPatient((current) => ({ ...current, [patientId]: "accepted" })); announce("Sample fact accepted into the demo timeline."); }}>Accept sample fact</button><button className="button button-secondary" onClick={() => { setReviewByPatient((current) => ({ ...current, [patientId]: "rejected" })); announce("Sample fact rejected."); }}>Reject sample fact</button></div></section>}

      {section === "timeline" && <section className="panel demo-panel"><h2>Medical timeline · {activePatient.name}</h2><p>2026 · {activePatient.conditions.split(";")[0]} · Patient reported</p><p>2026 · {patientId === "aarav" ? "Consultation summary" : "Paediatric consultation"} · Sample document</p>{activeReview === "accepted" && <p>{patientId === "aarav" ? "12 Feb 2026" : "03 Mar 2026"} · {activePatient.extractionCandidate} · Accepted in this browser session</p>}{activeReview === "rejected" && <p className="demo-disclaimer">The rejected sample fact is not shown as a timeline event.</p>}<p className="demo-disclaimer">Timeline entries are fictional and are not saved to an account.</p></section>}

      {section === "family" && <section className="panel demo-panel"><h2>Family profiles</h2><p>Current profile: <strong>{activePatient.name}</strong> · {activePatient.relationship}</p><div className="demo-actions">{patients.map((patient) => <button key={patient.id} className="button button-secondary" aria-pressed={patientId === patient.id} onClick={() => switchPatient(patient.id)}>{patient.id === "ira" ? "Switch to Ira's profile" : "Return to Aarav"}</button>)}</div><p className="demo-disclaimer">Profile switching changes the sample profile shown in this session. No family access is granted.</p></section>}

      {section === "emergency" && <section className="panel demo-panel"><h2>Emergency sharing</h2><p>Choose sample fields for the illustrative preview:</p>
        <fieldset className="demo-fieldset"><legend>Fields shown in preview</legend>{[["name", "Patient name"], ["blood", "Blood group"], ["allergies", "Allergies"], ["contact", "Emergency contact"]].map(([field, label]) => <label key={field}><input type="checkbox" checked={selectedFields.includes(field)} onChange={() => toggleField(field)}/>{label}</label>)}</fieldset>
        <div className="demo-actions"><button className="button" disabled={selectedFields.length === 0} onClick={() => { setQrShown(true); announce("Illustrative QR preview updated."); }}>Show QR preview</button><button className="button button-secondary" onClick={() => { setQrShown(false); announce("Illustrative QR preview hidden."); }}>Revoke preview</button></div>
        {qrShown && <div className="demo-qr-wrap"><div className="demo-qr" role="img" aria-label="Illustrative QR preview; not scannable">DEMO QR<br/>NOT SCANNABLE</div><ul aria-label="Selected fictional emergency details">{selectedFields.map((field) => <li key={field}><strong>{field === "name" ? "Patient name" : field === "blood" ? "Blood group" : field === "allergies" ? "Allergies" : "Emergency contact"}:</strong> {field === "name" ? activePatient.name : field === "blood" ? activePatient.blood : field === "allergies" ? activePatient.allergies : activePatient.contact}</li>)}</ul></div>}
        <p className="demo-disclaimer">This is not a QR access token. It cannot be scanned and has no expiry, access log, or security controls.</p></section>}

      <footer className="demo-footer"><Link href="/">Back to Medical Passport</Link><span>Simulated only · no backend · no account · no persistence</span></footer>

      {previewDocument && <div className="demo-modal-backdrop" role="presentation" onClick={() => setPreviewId(null)}><section className="demo-document-modal" role="dialog" aria-modal="true" aria-labelledby="document-preview-title" onClick={(event) => event.stopPropagation()}><button autoFocus className="button button-secondary demo-modal-close" onClick={() => setPreviewId(null)}>Close preview</button><h2 id="document-preview-title">{previewDocument.name}</h2><p>{previewDocument.date}</p><div className="demo-document-paper">{documentText[previewDocument.id].map((line) => <p key={line}>{line}</p>)}</div><p className="demo-disclaimer">Illustrative preview only · fictional sample content.</p></section></div>}
    </main>
  );
}
