"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

type Contact = { full_name: string; phone_number: string };
type DocFact = { text: string; record_date: string | null };
type Data = {
  updated_at: string;
  full_name?: string | null;
  blood_group?: string | null;
  known_allergies?: string | null;
  major_conditions?: string | null;
  current_medications?: string | null;
  emergency_contacts?: Contact[];
  document_allergies?: DocFact[];
  document_conditions?: DocFact[];
  document_medications?: DocFact[];
};

function Section({ title, hi, tone, children }: { title: string; hi: string; tone?: "alert"; children: React.ReactNode }) {
  return (
    <article className={tone === "alert" ? "emergency-block emergency-alert" : "emergency-block"}>
      <h2>{title} <span lang="hi">/ {hi}</span></h2>
      {children}
    </article>
  );
}

function Facts({ typed, docs, dated }: { typed?: string | null; docs?: DocFact[]; dated?: boolean }) {
  if (!typed && !docs?.length) return <p className="emergency-empty">Not recorded</p>;
  return (
    <>
      {typed && <p className="emergency-value">{typed}</p>}
      {docs?.map((d, i) => (
        <p className="emergency-value" key={i}>
          {d.text}
          <small>
            {" "}From a medical record{d.record_date ? ` dated ${d.record_date}` : ""}, confirmed by the patient
            {dated ? ". May have changed; verify." : "."}
          </small>
        </p>
      ))}
    </>
  );
}

export default function PublicEmergency() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<Data>(`/public/emergency/${encodeURIComponent(token)}`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "This link is unavailable or expired."));
  }, [token]);

  if (error) {
    return (
      <main className="public-emergency">
        <section className="panel">
          <h1>Link unavailable</h1>
          <p>This emergency link may have expired or been revoked. If this is an emergency, call 112.</p>
        </section>
      </main>
    );
  }
  if (!data) return <main className="public-emergency"><p role="status">Loading emergency information…</p></main>;

  const has = (k: keyof Data) => k in data;
  return (
    <main className="public-emergency">
      <p className="eyebrow">Medical Passport · Emergency summary / आपातकालीन सारांश</p>
      <h1>{data.full_name ?? "Emergency medical information"}</h1>
      {has("blood_group") && (
        <Section title="Blood group" hi="रक्त समूह">
          <p className="emergency-big">{data.blood_group || "Not recorded"}</p>
        </Section>
      )}
      {(has("known_allergies") || has("document_allergies")) && (
        <Section title="Allergies" hi="एलर्जी" tone="alert">
          <Facts typed={data.known_allergies} docs={data.document_allergies} />
        </Section>
      )}
      {(has("major_conditions") || has("document_conditions")) && (
        <Section title="Medical conditions" hi="बीमारियाँ">
          <Facts typed={data.major_conditions} docs={data.document_conditions} />
        </Section>
      )}
      {(has("current_medications") || has("document_medications")) && (
        <Section title="Medications" hi="दवाइयाँ">
          <Facts typed={data.current_medications} docs={data.document_medications} dated />
        </Section>
      )}
      {data.emergency_contacts && (
        <Section title="Emergency contacts" hi="आपातकालीन संपर्क">
          {data.emergency_contacts.length === 0 && <p className="emergency-empty">Not recorded</p>}
          {data.emergency_contacts.map((c, i) => (
            <a className="call-button" key={i} href={`tel:${c.phone_number}`}>
              Call {c.full_name} · {c.phone_number}
            </a>
          ))}
        </Section>
      )}
      <p className="field-hint">
        Patient-reported information, not verified by a clinician. Confirm with the patient or care team. Last updated{" "}
        {new Date(data.updated_at).toLocaleString()}. Emergency services: 112.
      </p>
    </main>
  );
}
