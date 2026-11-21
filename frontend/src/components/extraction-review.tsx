"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { useLanguage } from "@/lib/language";

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
  ai_consent_granted?: boolean;
  ai_provider_name?: string | null;
  ai_provider_at?: string | null;
  candidates: Candidate[];
  warnings?: string[];
  created_events?: number;
  skipped_duplicates?: number;
};

const FIELD_LABELS: Record<string, string> = {
  patient_name: "Patient name",
  age: "Age",
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
  const { t } = useLanguage();
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const [aiConsent, setAiConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<Extraction>(`/documents/${documentId}/extraction`)
      .then(setExtraction)
      .catch(() => setExtraction(null)); // no extraction yet
  }, [documentId]);

  useEffect(() => {
    apiRequest<{ available: boolean }>(`/documents/${documentId}/ai-capability`)
      .then((value) => setAiAvailable(value.available))
      .catch(() => setAiAvailable(false));
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
      () => apiRequest<Extraction>(`/documents/${documentId}/process`, { method: "POST", body: JSON.stringify({ ai_consent: aiConsent }) }),
      "Processing failed. Retry.",
    );
    if (result) {
      setExtraction(result);
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
        <strong>{t(FIELD_LABELS[c.field] ?? c.field)}</strong>
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
      <h3>{t("Text extraction and review")}</h3>
      <p>
        Medical Passport reads the document and suggests facts. Nothing reaches your timeline or emergency
        card until you accept it.
      </p>
      {canEdit && extraction?.status !== "confirmed" && (
        <>
        {aiAvailable && <label className="consent-line"><input type="checkbox" checked={aiConsent} onChange={(event) => setAiConsent(event.target.checked)} /> I agree to send redacted OCR text for this document to the configured AI provider for suggestions.</label>}
        <button className="button" disabled={busy} onClick={() => void process()}>
          {busy ? "Working…" : processingStatus === "failed" ? "Retry extraction" : extraction ? "Re-run extraction" : "Run OCR and extraction"}
        </button>
        </>
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
          {extraction.ai_provider_name && extraction.ai_provider_at && <p>AI suggestions from {extraction.ai_provider_name} · {new Date(extraction.ai_provider_at).toLocaleString()}</p>}
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
