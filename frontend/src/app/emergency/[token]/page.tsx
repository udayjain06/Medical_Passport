"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { LanguageSwitcher, useLanguage } from "@/lib/i18n";

type Contact = { full_name: string; phone_number: string };
type DocFact = { text: string; record_date: string | null };
type Data = {
  demo_data?: boolean;
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
  const { language } = useLanguage();
  return (
    <article className={tone === "alert" ? "emergency-block emergency-alert" : "emergency-block"}>
      <h2>{language === "hi" ? hi : title} <span lang={language === "hi" ? "en" : "hi"}>/ {language === "hi" ? title : hi}</span></h2>
      {children}
    </article>
  );
}

function Facts({ typed, docs, dated }: { typed?: string | null; docs?: DocFact[]; dated?: boolean }) {
  const { language, t } = useLanguage();
  if (!typed && !docs?.length) return <p className="emergency-empty">{t("notRecorded")}</p>;
  return (
    <>
      {typed && <p className="emergency-value">{typed}</p>}
      {docs?.map((d, i) => (
        <p className="emergency-value" key={i}>
          {d.text}
          <small>
            {language === "hi" ? " " : " From a medical record"}{d.record_date ? ` ${language === "hi" ? "दिनांक" : "dated"} ${d.record_date}` : ""}{language === "hi" ? ", रोगी द्वारा पुष्टि की गई" : ", confirmed by the patient"}
            {dated ? (language === "hi" ? "। बदल सकती है; पुष्टि करें।" : ". May have changed; verify.") : language === "hi" ? "।" : "."}
          </small>
        </p>
      ))}
    </>
  );
}

export default function PublicEmergency() {
  const { language, t } = useLanguage();
  const { token } = useParams<{ token: string }>();
  const [result, setResult] = useState<{ token: string; data: Data | null; error: string }>({
    token: "",
    data: null,
    error: "",
  });
  const requestRef = useRef<{ token: string; request: Promise<Data> } | null>(null);
  const data = result.token === token ? result.data : null;
  const error = result.token === token ? result.error : "";

  useEffect(() => {
    const request = requestRef.current?.token === token
      ? requestRef.current.request
      : apiRequest<Data>(`/public/emergency/${encodeURIComponent(token)}`);
    requestRef.current = { token, request };

    let active = true;
    request
      .then((result) => {
        if (active) setResult({ token, data: result, error: "" });
      })
      .catch((e) => {
        if (active) {
          setResult({
            token,
            data: null,
            error: e instanceof Error ? e.message : "This link is unavailable or expired.",
          });
        }
      });
    return () => {
      active = false;
    };
  }, [token]);

  if (error) {
    return (
      <main className="public-emergency">
        <section className="panel">
          <LanguageSwitcher />
          <h1>{t("linkUnavailable")}</h1>
          <p>{t("emergencyExpired")}</p>
        </section>
      </main>
    );
  }
  if (!data) return <main className="public-emergency"><LanguageSwitcher /><p role="status">{t("loadingEmergency")}</p></main>;

  const has = (k: keyof Data) => k in data;
  return (
    <main className="public-emergency">
      <LanguageSwitcher />
      <p className="eyebrow">Medical Passport · {language === "hi" ? "आपातकालीन सारांश" : "Emergency summary"}</p>
      {data.demo_data && <p className="demo-public-banner" role="note">SYNTHETIC DEMO DATA — NOT A REAL PATIENT</p>}
      <h1>{data.full_name ?? "Emergency medical information"}</h1>
      {has("blood_group") && (
        <Section title="Blood group" hi="रक्त समूह">
          <p className="emergency-big">{data.blood_group || t("notRecorded")}</p>
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
          {data.emergency_contacts.length === 0 && <p className="emergency-empty">{t("notRecorded")}</p>}
          {data.emergency_contacts.map((c, i) => (
            <a className="call-button" key={i} href={`tel:${c.phone_number}`}>
              {language === "hi" ? `${c.full_name} को कॉल करें · ${c.phone_number}` : `Call ${c.full_name} · ${c.phone_number}`}
            </a>
          ))}
        </Section>
      )}
      <p className="field-hint">
        {t("patientReportedDisclaimer")} {language === "hi" ? "अंतिम अपडेट" : "Last updated"}{" "}
        {new Date(data.updated_at).toLocaleString(language === "hi" ? "hi-IN" : "en-IN")}.
      </p>
    </main>
  );
}
