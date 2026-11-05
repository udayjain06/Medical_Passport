"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "@/lib/api";

type Profile = { id: string; full_name: string; is_primary: boolean; role: string; relationship?: string | null };

export default function Family() {
  const router = useRouter();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [fullName, setFullName] = useState("");
  const [relationship, setRelationship] = useState("Child");
  const [authority, setAuthority] = useState(false);
  const [targetProfile, setTargetProfile] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function load() {
    try {
      const items = await apiRequest<Profile[]>("/profiles");
      setProfiles(items);
      if (!targetProfile) setTargetProfile(items.find((p) => p.role === "owner")?.id ?? "");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load profiles"); }
  }
  useEffect(() => { apiRequest<Profile[]>("/profiles").then((items) => { setProfiles(items); setTargetProfile(items.find((p) => p.role === "owner")?.id ?? ""); }).catch((e) => setError(e instanceof Error ? e.message : "Could not load profiles")); }, []);

  async function addDependent(e: React.FormEvent) {
    e.preventDefault(); setError(""); setSuccess("");
    try {
      await apiRequest("/profiles", { method: "POST", body: JSON.stringify({ full_name: fullName, relationship_label: relationship, authority_confirmed: authority }) });
      setSuccess("Dependent profile created. Switch profiles in the top navigation."); setFullName(""); setAuthority(false); await load();
    } catch (x) { setError(x instanceof Error ? x.message : "Could not create dependent profile"); }
  }

  async function grant(e: React.FormEvent) {
    e.preventDefault(); setError(""); setSuccess("");
    try {
      if (!targetProfile) throw new Error("Choose a profile you own.");
      await apiRequest(`/profiles/${targetProfile}/access`, { method: "POST", body: JSON.stringify({ email, role }) });
      setSuccess(`Access granted to ${email}.`); setEmail(""); await load();
    } catch (x) { setError(x instanceof Error ? x.message : "Could not grant access"); }
  }

  async function archiveDependent(profile: Profile) {
    if (!window.confirm(`Archive ${profile.full_name}? Their records are retained, but the profile and its active emergency links will be disabled.`)) return;
    setError(""); setSuccess("");
    try {
      await apiRequest(`/profiles/${profile.id}`, { method: "DELETE" });
      if (window.sessionStorage.getItem("active_patient_profile") === profile.id) {
        window.sessionStorage.removeItem("active_patient_profile");
        router.replace("/family");
        return;
      }
      setSuccess(`${profile.full_name} was archived. Their medical records were retained.`);
      await load();
    } catch (x) { setError(x instanceof Error ? x.message : "Could not archive dependent profile"); }
  }

  return <main className="page-wrap">
    <header className="page-heading"><p className="eyebrow">Permission-based care</p><h1>Family profiles</h1><p>Manage a dependent only when you have their consent or lawful authority. Adult family members should create their own account and authorize sharing.</p></header>
    <section className="panel"><h2>Profiles available to this account</h2>{profiles.length === 0 ? <p>No profiles shared with you.</p> : profiles.map((p) => <article className="share-row" key={p.id}><strong>{p.full_name}</strong><span>{p.role}{p.relationship ? ` · ${p.relationship}` : p.is_primary ? " · primary" : ""}</span>{p.role === "owner" && !p.is_primary && <button className="button button-secondary button-small" onClick={() => void archiveDependent(p)}>Archive profile</button>}</article>)}</section>
    <section className="panel share-list"><h2>Add a dependent profile</h2><p>Confirm consent or lawful authority before adding a child or dependent. This confirmation is recorded as your attestation; the app cannot verify legal authority.</p><form className="timeline-add" onSubmit={addDependent}><input required maxLength={120} aria-label="Dependent full name" placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)}/><select aria-label="Relationship" value={relationship} onChange={(e) => setRelationship(e.target.value)}><option>Child</option><option>Parent</option><option>Spouse</option><option>Other dependent</option></select><label className="consent-line"><input type="checkbox" checked={authority} onChange={(e) => setAuthority(e.target.checked)}/>I have consent or lawful authority</label><button className="button" disabled={!authority}>Add dependent</button></form></section>
    <section className="panel share-list"><h2>Grant account access</h2><p>The invited family member must already have a Medical Passport account. They may revoke their own access or the profile owner may revoke it.</p><form className="timeline-add" onSubmit={grant}><select aria-label="Profile to share" value={targetProfile} onChange={(e) => setTargetProfile(e.target.value)}>{profiles.filter((p) => p.role === "owner").map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}</select><input type="email" required aria-label="Family member account email" placeholder="Account email" value={email} onChange={(e) => setEmail(e.target.value)}/><select aria-label="Access role" value={role} onChange={(e) => setRole(e.target.value)}><option value="viewer">Read-only viewer</option><option value="editor">Editor</option><option value="caregiver">Caregiver</option></select><button className="button">Grant access</button></form></section>
    {error && <p className="form-error" role="alert">{error}</p>}{success && <p className="form-success" role="status">{success}</p>}
  </main>;
}
