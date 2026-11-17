"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";

type Candidate = {
  candidate_id?: string;
  field: string;
  value: string;
  source_page?: number;
  original_value?: string;
  confidence: number;
  review_status: "pending" | "accepted" | "rejected" | "confirmed" | "duplicate_skipped";
};

type Extraction = {
  status: string;
  ocr_text: string | null;
  engine_version: string;
  candidates: Candidate[];
  warnings?: string[];
  created_events?: number;
  skipped_duplicates?: number;
  ai_consent?: boolean;
  ai_consent_at?: string | null;
  ai_provider?: string | null;
  ai_processed_at?: string | null;
};

const FIELD_LABELS: Record<string, string> = {
  patient_name: "Patient name",
  doctor_name: "Doctor",
  hospital_name: "Hospital / lab",
  document_date: "Document date",
  diagnosis: "Diagnosis",
  condition: "Condition",
  allergy: "Allergy",
  medication: "Medication",
  procedure: "Procedure",
  lab_test: "Lab result",
  admission_date: "Admission date",
  discharge_date: "Discharge date",
  follow_up_date: "Follow-up date",
  source_text: "Unstructured text",
};
const DETAIL_FIELDS = new Set(["patient_name", "doctor_name", "hospital_name", "document_date"]);
const LOW_CONFIDENCE = 0.6;
const TIMELINE_FIELDS = new Set([
  "diagnosis", "condition", "allergy", "medication", "procedure", "lab_test",
  "admission_date", "discharge_date", "follow_up_date", "source_text",
]);

type Props = {
  documentId: string;
  canEdit: boolean;
  processingStatus: string;
  onChanged: () => void;
};

export function ExtractionReview({ documentId, canEdit, processingStatus, onChanged }: Props) {
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [externalAiConfigured, setExternalAiConfigured] = useState(false);
  const [aiConsent, setAiConsent] = useState({ documentId, checked: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<{ external_ai_configured: boolean }>("/auth/ai-capabilities")
      .then((capabilities) => setExternalAiConfigured(capabilities.external_ai_configured))
      .catch(() => setExternalAiConfigured(false));
    apiRequest<Extraction>(`/documents/${documentId}/extraction`)
      .then(setExtraction)
      .catch(() => setExtraction(null)); // no extraction yet
  }, [documentId]);

  async function run<T>(task: () => Promise<T>, fallback: string) {
    setBusy(true);
    setError("");
    try {
      return await task();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : fallback);
    } finally {
      setBusy(false);
    }
  }

  async function process() {
    const result = await run(
      () => apiRequest<Extraction>(`/documents/${documentId}/process`, {
        method: "POST",
        body: JSON.stringify({ ai_consent: aiConsent.documentId === documentId && aiConsent.checked }),
      }),
      "Processing failed. Retry.",
    );
    if (result) {
      setExtraction(result);
      setAiConsent({ documentId, checked: false });
      onChanged();
    }
  }

  function update(index: number, patch: Partial<Candidate>) {
    setExtraction((current) =>
      current
        ? { ...current, candidates: current.candidates.map((c, i) => (i === index ? { ...c, ...patch } : c)) }
        : current,
    );
  }

  function acceptConfident() {
    setExtraction((current) =>
      current
        ? {
            ...current,
            candidates: current.candidates.map((c) =>
              c.review_status === "pending" && c.confidence >= 0.8 && c.field !== "source_text"
                ? { ...c, review_status: "accepted" }
                : c,
            ),
          }
        : current,
    );
  }

  async function confirm() {
    if (!extraction) return;
    const result = await run(async () => {
      await apiRequest(`/documents/${documentId}/extraction`, {
        method: "PUT",
        body: JSON.stringify({ candidates: extraction.candidates }),
      });
      return apiRequest<Extraction>(`/documents/${documentId}/extraction/confirm`, { method: "POST" });
    }, "Could not confirm. Retry.");
    if (result) {
      setExtraction(result);
      onChanged();
    }
  }

  async function reject() {
    const result = await run(
      () => apiRequest<Extraction>(`/documents/${documentId}/extraction/reject`, { method: "POST" }),
      "Could not reject.",
    );
    if (result) {
      setExtraction(result);
      onChanged();
    }
  }

  const open = extraction?.status === "needs_review";
  const accepted = extraction?.candidates.filter((c) => c.review_status === "accepted" && TIMELINE_FIELDS.has(c.field)).length ?? 0;
  const details = extraction?.candidates.map((c, i) => ({ c, i })).filter(({ c }) => DETAIL_FIELDS.has(c.field)) ?? [];
  const facts = extraction?.candidates.map((c, i) => ({ c, i })).filter(({ c }) => !DETAIL_FIELDS.has(c.field)) ?? [];

  const renderRow = ({ c, i }: { c: Candidate; i: number }) => (
    <div className={`candidate candidate-${c.review_status}`} key={c.candidate_id ?? i}>
      <div className="candidate-head">
        <strong>{FIELD_LABELS[c.field] ?? c.field}</strong>
        <span className={c.confidence < LOW_CONFIDENCE ? "badge badge-warn" : "badge"}>
          {Math.round(c.confidence * 100)}% · page {c.source_page ?? "?"}
        </span>
      </div>
      <textarea
        aria-label={`${FIELD_LABELS[c.field] ?? c.field} text`}
        disabled={!canEdit || !open}
        value={c.value}
        rows={2}
        onChange={(e) => update(i, { value: e.target.value })}
      />
      {c.confidence < LOW_CONFIDENCE && open && (
        <p className="field-hint">Low confidence. Compare with the original before accepting.</p>
      )}
      {canEdit && open ? (
        <div className="review-actions">
          <button
            type="button"
            className={c.review_status === "accepted" ? "button button-small" : "button button-small button-secondary"}
            aria-pressed={c.review_status === "accepted"}
            onClick={() => update(i, { review_status: c.review_status === "accepted" ? "pending" : "accepted" })}
          >
            {c.review_status === "accepted" ? "Accepted" : "Accept"}
          </button>
          <button
            type="button"
            className={c.review_status === "rejected" ? "button button-small button-danger" : "button button-small button-secondary"}
            aria-pressed={c.review_status === "rejected"}
            onClick={() => update(i, { review_status: c.review_status === "rejected" ? "pending" : "rejected" })}
          >
            {c.review_status === "rejected" ? "Rejected" : "Reject"}
          </button>
        </div>
      ) : (
        <p className="field-hint">{c.review_status.replace("_", " ")}</p>
      )}
    </div>
  );

  return (
    <section className="review-box">
      <h3>Text extraction and review</h3>
      <p>
        Medical Passport reads the document and suggests facts. Nothing reaches your timeline or emergency
        card until you accept it.
      </p>
      {externalAiConfigured && canEdit && extraction?.status !== "confirmed" && (
        <label className="ai-consent">
          <input
            type="checkbox"
            checked={aiConsent.documentId === documentId && aiConsent.checked}
            onChange={(event) => setAiConsent({ documentId, checked: event.target.checked })}
          />
          <span>Allow this document’s OCR text to be processed by the configured AI provider for this run. Patient name and long number-like identifiers are removed first.</span>
        </label>
      )}
      {extraction?.ai_provider && extraction.ai_processed_at && (
        <p className="field-hint">External AI processing: {extraction.ai_provider} · {new Date(extraction.ai_processed_at).toLocaleString()} (sent after consent with identifiers redacted).</p>
      )}
      {canEdit && extraction?.status !== "confirmed" && (
        <button className="button" disabled={busy} onClick={() => void process()}>
          {busy ? "Working…" : processingStatus === "failed" ? "Retry extraction" : extraction ? "Re-run extraction" : "Run OCR and extraction"}
        </button>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
      {extraction?.warnings?.map((w) => (
        <p className="form-error" role="alert" key={w}>{w}</p>
      ))}
      {extraction && (
        <>
          <p>
            Status: <strong>{extraction.status.replace("_", " ")}</strong> · engine: {extraction.engine_version}
          </p>
          {extraction.status === "confirmed" && extraction.created_events !== undefined && (
            <p role="status">
              {extraction.created_events} added to your <Link href="/timeline">timeline</Link>
              {extraction.skipped_duplicates ? `, ${extraction.skipped_duplicates} skipped as already recorded` : ""}.
            </p>
          )}
          {details.length > 0 && <h4>Document details</h4>}
          {details.map(renderRow)}
          {facts.length > 0 && <h4>Medical facts</h4>}
          {facts.map(renderRow)}
          {extraction.candidates.length === 0 && <p>No readable text was found. Try a clearer photo or scan.</p>}
          {extraction.ocr_text && (
            <details>
              <summary>OCR source text</summary>
              <pre>{extraction.ocr_text}</pre>
            </details>
          )}
          {canEdit && open && (
            <div className="review-actions">
              <button className="button button-secondary" type="button" onClick={acceptConfident}>
                Accept all 80%+ matches
              </button>
              <button className="button" disabled={busy || accepted === 0} onClick={() => void confirm()}>
                Add {accepted} accepted to timeline
              </button>
              <button className="button button-secondary" disabled={busy} onClick={() => void reject()}>
                Discard suggestions
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
