"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiRequest } from "@/lib/api";

type Event = {
  id: string;
  title: string;
  category: string;
  event_date: string | null;
  summary: string | null;
  source_document_id: string | null;
  source_extraction_id: string | null;
  source_candidate_id: string | null;
  source_document_filename: string | null;
  source_document_checksum: string | null;
  source_page: number | null;
  provenance: string;
  verification_status: string;
  conflict_group: string | null;
  uncertainty_note: string | null;
  can_edit: boolean;
};
type Document = { id: string; original_filename: string };
type Profile = { id: string; role: string };
type Draft = {
  title: string;
  category: string;
  event_date: string;
  summary: string;
  verification_status: string;
  conflict_group: string;
  uncertainty_note: string;
};

const categories = ["Consultation", "Diagnosis", "Prescription", "Lab test", "Surgery", "Admission", "Discharge", "Allergy", "Vaccination", "Medical observation", "Follow-up"];
const emptyDraft: Draft = { title: "", category: "Medical observation", event_date: "", summary: "", verification_status: "patient_entered", conflict_group: "", uncertainty_note: "" };

export default function TimelineManager() {
  const [events, setEvents] = useState<Event[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [canEdit, setCanEdit] = useState(true);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState("");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    const query = new URLSearchParams({ sort });
    if (search) query.set("search", search);
    if (category) query.set("category", category);
    if (source) query.set("source_document_id", source);
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    if (status) query.set("verification_status", status);
    try {
      setEvents(await apiRequest<Event[]>(`/timeline?${query}`));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load timeline");
    }
  }, [category, dateFrom, dateTo, search, sort, source, status]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void load());
    return () => window.cancelAnimationFrame(frame);
  }, [load]);
  useEffect(() => {
    apiRequest<Document[]>("/documents")
      .then(setDocuments)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load source documents"));
  }, []);
  useEffect(() => {
    apiRequest<Profile[]>("/profiles").then((profiles) => {
      const activeId = window.sessionStorage.getItem("active_patient_profile");
      const active = profiles.find((profile) => profile.id === activeId) ?? profiles.find((profile) => profile.role === "owner");
      setCanEdit(active?.role !== "viewer");
    }).catch((caught) => setError(caught instanceof Error ? caught.message : "Could not check profile permissions"));
  }, []);

  function beginEdit(event: Event) {
    setEditing(event.id);
    setDraft({
      title: event.title,
      category: event.category,
      event_date: event.event_date ?? "",
      summary: event.summary ?? "",
      verification_status: event.verification_status,
      conflict_group: event.conflict_group ?? "",
      uncertainty_note: event.uncertainty_note ?? "",
    });
    setError("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setSuccess("");
    const payload = {
      ...draft,
      event_date: draft.event_date || null,
      summary: draft.summary || null,
      conflict_group: draft.conflict_group || null,
      uncertainty_note: draft.uncertainty_note || null,
    };
    try {
      await apiRequest(editing ? `/timeline/${editing}` : "/timeline", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setDraft(emptyDraft); setEditing(null); setSuccess(editing ? "Event updated." : "Event added.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save event");
    }
  }

  async function remove(event: Event) {
    if (!window.confirm(`Delete “${event.title}” from this timeline?`)) return;
    setError(""); setSuccess("");
    try {
      await apiRequest(`/timeline/${event.id}`, { method: "DELETE" });
      setSuccess("Timeline event deleted.");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete event");
    }
  }

  return <main className="page-wrap">
    <header className="page-heading"><p className="eyebrow">Source-linked history</p><h1>Medical timeline</h1><p>Patient-confirmed facts from records and entries you add yourself. Mark uncertain or conflicting history so it stays visible for review.</p></header>
    {canEdit ? <section className="panel">
      <h2>{editing ? "Edit timeline event" : "Add a patient-entered event"}</h2>
      <form className="form-grid" onSubmit={(event) => void save(event)}>
        <label className="field">Event title<input required maxLength={200} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
        <label className="field">Category<select aria-label="Event category" value={draft.category} onChange={(event) => setDraft({ ...draft, category: event.target.value })}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="field">Event date<input type="date" value={draft.event_date} onChange={(event) => setDraft({ ...draft, event_date: event.target.value })} /></label>
        <label className="field">Note<textarea maxLength={5000} value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} /></label>
        <label className="field">Review status<select aria-label="Event review status" value={draft.verification_status} onChange={(event) => setDraft({ ...draft, verification_status: event.target.value })}><option value="patient_entered">Patient entered</option><option value="confirmed">Confirmed</option><option value="uncertain">Uncertain</option><option value="conflict">Conflicting information</option></select></label>
        {draft.verification_status === "conflict" && <label className="field">Conflict group<input required maxLength={80} placeholder="For example: medication-dose-review" value={draft.conflict_group} onChange={(event) => setDraft({ ...draft, conflict_group: event.target.value })} /></label>}
        {draft.verification_status === "uncertain" && <label className="field">Why is this uncertain?<textarea required maxLength={1000} value={draft.uncertainty_note} onChange={(event) => setDraft({ ...draft, uncertainty_note: event.target.value })} /></label>}
        <div className="form-actions"><button className="button">{editing ? "Save changes" : "Add event"}</button>{editing && <button type="button" className="button button-secondary" onClick={() => { setEditing(null); setDraft(emptyDraft); }}>Cancel edit</button>}</div>
      </form>
    </section> : <p className="verification-note">This profile is read-only for your account. You can review its timeline entries.</p>}
    <section className="panel" aria-label="Timeline filters">
      <h2>Find events</h2>
      <div className="timeline-tools">
        <input aria-label="Search timeline" placeholder="Search title or note" value={search} onChange={(event) => setSearch(event.target.value)} />
        <select aria-label="Filter category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
        <select aria-label="Filter source document" value={source} onChange={(event) => setSource(event.target.value)}><option value="">All sources</option>{documents.map((document) => <option key={document.id} value={document.id}>{document.original_filename}</option>)}</select>
        <label>From<input aria-label="Date from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label>
        <label>Through<input aria-label="Date through" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></label>
        <select aria-label="Filter review status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All review states</option><option value="patient_entered">Patient entered</option><option value="confirmed">Confirmed</option><option value="uncertain">Uncertain</option><option value="conflict">Conflict</option></select>
        <select aria-label="Sort timeline" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select>
      </div>
    </section>
    {error && <p className="form-error" role="alert">{error}<button className="button button-secondary button-small" onClick={() => void load()}>Retry</button></p>}
    {success && <p className="form-success" role="status">{success}</p>}
    {events.length === 0 ? <div className="empty-state"><strong>No timeline entries match these filters</strong><p>Confirm reviewed extraction candidates or add an event.</p></div> : <div className="timeline-list">{events.map((item) => <article className="timeline-item" key={item.id}>
      <time>{item.event_date || "Date not recorded"}</time><div><h2>{item.title}</h2><p>{item.summary}</p><span className="status-pill">{item.verification_status.replaceAll("_", " ")}</span>
        {item.uncertainty_note && <p>Uncertainty: {item.uncertainty_note}</p>}{item.conflict_group && <p>Conflict group: {item.conflict_group}</p>}
        {item.source_document_id && <p><Link href={`/documents?document=${item.source_document_id}`}>Open source document{item.source_page ? ` · page ${item.source_page}` : ""}</Link></p>}
        {!item.source_document_id && item.source_document_filename && <p>Source retained after document removal: {item.source_document_filename}{item.source_document_checksum ? ` · SHA-256 ${item.source_document_checksum}` : ""}</p>}
        {item.source_extraction_id && <p>Extraction run {item.source_extraction_id}; candidate {item.source_candidate_id}</p>}
        {item.can_edit && <div className="form-actions"><button className="button button-secondary button-small" onClick={() => beginEdit(item)}>Edit</button><button className="button button-secondary button-small" onClick={() => void remove(item)}>Delete</button></div>}
      </div></article>)}</div>}
  </main>;
}
