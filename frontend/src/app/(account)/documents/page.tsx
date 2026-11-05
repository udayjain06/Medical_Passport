"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiFetch, apiRequest } from "@/lib/api";
import { DocumentSheet } from "@/components/document-sheet";

type Document = { id: string; original_filename: string; file_format: string; file_size: number; category: string; document_date: string | null; processing_status: string; created_at: string; can_edit: boolean };
type Profile = { id: string; role: string };
type Extraction = { status:string; ocr_text:string|null; engine_version:string; candidates:Array<{field:string;value:string;source_page?:number;original_value?:string;confidence:number;review_status:string}> };
const categories = ["Prescription", "Laboratory Report", "Blood Report", "Discharge Summary", "Medical Certificate", "Imaging Report", "Vaccination Record", "Other"];

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Document | null>(null);
  const [preview, setPreview] = useState<{ id: string; url: string } | null>(null);
  const [previewError, setPreviewError] = useState<{ id: string; message: string } | null>(null);
  const [extraction, setExtraction] = useState<Extraction|null>(null);
  const [processing, setProcessing] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams();
      if (search) query.set("search", search);
      if (category) query.set("category", category);
      setDocs(await apiRequest<Document[]>(`/documents?${query}`));
      setError("");
    } catch (e) { setError(e instanceof ApiError ? e.message : "Could not load documents."); }
  }, [search, category]);
  useEffect(() => {
    const query = new URLSearchParams();
    if (search) query.set("search", search);
    if (category) query.set("category", category);
    apiRequest<Document[]>(`/documents?${query}`).then(setDocs).catch(e => setError(e instanceof ApiError ? e.message : "Could not load documents."));
  }, [search, category]);
  useEffect(() => {
    apiRequest<Profile[]>("/profiles").then((profiles) => {
      const activeId = window.sessionStorage.getItem("active_patient_profile");
      const active = profiles.find((profile) => profile.id === activeId) ?? profiles.find((profile) => profile.role === "owner");
      setCanEdit(active?.role !== "viewer");
    }).catch((e) => setError(e instanceof ApiError ? e.message : "Could not check profile permissions."));
  }, []);
  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    if (!selected) return;
    apiFetch(`/documents/${selected.id}/content`)
      .then(async (response) => {
        if (!response.ok) throw new ApiError("This document could not be opened.", response.status);
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (active) setPreview({ id: selected.id, url: objectUrl });
        else URL.revokeObjectURL(objectUrl);
      })
      .catch((caught: unknown) => {
        if (active) setPreviewError({ id: selected.id, message: caught instanceof Error ? caught.message : "This document could not be opened." });
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selected]);

  function upload(file?: File) {
    if (!file) return;
    setBusy(true); setError(""); setProgress(0);
    const body = new FormData(); body.append("file", file); body.append("category", "Other");
    const request = new XMLHttpRequest(); request.open("POST", "/api/documents"); request.withCredentials = true;
    const activeProfile = window.sessionStorage.getItem("active_patient_profile"); if(activeProfile)request.setRequestHeader("X-Patient-Profile",activeProfile);
    request.upload.onprogress = (event) => { if (event.lengthComputable) setProgress(Math.round(event.loaded / event.total * 100)); };
    request.onload = () => { setBusy(false); if (request.status >= 200 && request.status < 300) void load(); else { try { setError(JSON.parse(request.responseText).detail ?? "Upload failed."); } catch { setError("Upload failed. Please retry."); } } };
    request.onerror = () => { setBusy(false); setError("Could not reach the service. Please retry."); };
    request.send(body);
  }

  async function remove(doc: Document) {
    if (!window.confirm(`Delete ${doc.original_filename}? This cannot be undone.`)) return;
    try { await apiRequest<void>(`/documents/${doc.id}`, { method: "DELETE" }); setSelected(null); await load(); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Delete failed. Please retry."); }
  }
  async function update(doc: Document, next: string) {
    try { const saved = await apiRequest<Document>(`/documents/${doc.id}`, { method: "PATCH", body: JSON.stringify({ category: next }) }); setDocs(current => current.map(item => item.id === saved.id ? saved : item)); setSelected(saved); }
    catch (e) { setError(e instanceof ApiError ? e.message : "Update failed. Please retry."); }
  }

  async function processDocument(doc: Document) { setProcessing(true); setError(""); try { setExtraction(await apiRequest<Extraction>(`/documents/${doc.id}/process`,{method:"POST"})); await load(); } catch(e) { setError(e instanceof ApiError?e.message:"Processing failed. Retry."); } finally { setProcessing(false); } }
  async function confirmExtraction(doc: Document) { if(!extraction)return; try { await apiRequest<Extraction>(`/documents/${doc.id}/extraction`,{method:"PUT",body:JSON.stringify({candidates:extraction.candidates})}); const confirmed=await apiRequest<Extraction>(`/documents/${doc.id}/extraction/confirm`,{method:"POST"}); setExtraction(confirmed); setDocs(current=>current.map(item=>item.id===doc.id?{...item,processing_status:confirmed.status}:item)); } catch(e) { setError(e instanceof ApiError?e.message:"Could not confirm extraction."); } }
  async function rejectExtraction(doc: Document) { try { setExtraction(await apiRequest<Extraction>(`/documents/${doc.id}/extraction/reject`,{method:"POST"})); } catch(e) { setError(e instanceof ApiError?e.message:"Could not reject extraction."); } }
  async function loadExtraction(doc:Document) { setExtraction(null); try { setExtraction(await apiRequest<Extraction>(`/documents/${doc.id}/extraction`)); } catch { /* no extraction yet */ } }
  useEffect(() => {
    const target = new URLSearchParams(window.location.search).get("document");
    const doc = docs.find(item => item.id === target);
    if (doc) queueMicrotask(() => { setSelected(doc); void loadExtraction(doc); });
  }, [docs]);

  return <main className="page-wrap vault-wrap">
    <header className="page-heading"><p className="eyebrow">Your private records</p><h1>Medical document vault</h1><p>Keep prescriptions, reports, and summaries together. Files are private to your account.</p></header>
    {canEdit ? <section className="vault-upload" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}>
      <span className="upload-icon" aria-hidden="true">↥</span><h2>Add a document</h2><p>PDF, JPG, or PNG · up to 10 MB</p>
      <input ref={input} hidden type="file" accept="application/pdf,image/jpeg,image/png" onChange={e => upload(e.target.files?.[0])}/>
      <button type="button" className="button" disabled={busy} onClick={() => input.current?.click()}>{busy ? "Uploading…" : "Choose a file"}</button>
      {busy && <progress className="upload-progress" value={progress} max={100} aria-label="Upload progress"/>}{error && <p className="form-error" role="alert">{error} <button className="text-button" onClick={() => void load()}>Retry</button></p>}
    </section> : <p className="verification-note">This profile is read-only for your account. You can view and download its records.</p>}
    <section className="vault-list"><div className="vault-toolbar"><div><h2>Your documents</h2><p>{docs.length} {docs.length === 1 ? "record" : "records"}</p></div><div className="vault-filters"><input aria-label="Search documents" placeholder="Search filename" value={search} onChange={e => setSearch(e.target.value)}/><select aria-label="Filter by category" value={category} onChange={e => setCategory(e.target.value)}><option value="">All categories</option>{categories.map(item => <option key={item}>{item}</option>)}</select></div></div>
      {docs.length === 0 ? <div className="empty-state"><strong>{error ? "Documents could not be loaded" : "Your vault is ready"}</strong><p>{error ? "Retry the request, or upload a document to begin." : "Upload your first medical record to see it here."}</p>{error && <button className="button button-secondary button-small" onClick={() => void load()}>Retry</button>}</div> : <div className="document-grid">{docs.map(doc => <article className="document-card" key={doc.id}><button type="button" className="document-open" onClick={() => {setSelected(doc);void loadExtraction(doc)}}><span className="document-mark">{doc.file_format.toUpperCase()}</span><strong>{doc.original_filename}</strong><small>{doc.category} · {(doc.file_size / 1024 / 1024).toFixed(2)} MB</small></button><button className="text-button" onClick={() => {setSelected(doc);void loadExtraction(doc)}}>Details</button></article>)}</div>}
    </section>
    {selected && <DocumentSheet onDismiss={() => setSelected(null)}>
      <header className="sheet-content-header"><div><p className="eyebrow">Document details</p><h2>{selected.original_filename}</h2></div></header>
      <div className="field"><label htmlFor="doc-category">Category</label><select id="doc-category" disabled={!selected.can_edit} value={selected.category} onChange={e => void update(selected, e.target.value)}>{categories.map(item => <option key={item}>{item}</option>)}</select></div>
      <p className="field-hint">Uploaded {new Date(selected.created_at).toLocaleDateString()} · Processing: {selected.processing_status}</p>
      {preview?.id === selected.id ? <iframe className="document-preview" title={`Preview ${selected.original_filename}`} src={preview.url}/> : <p className={previewError?.id === selected.id ? "form-error" : "loading"} role={previewError?.id === selected.id ? "alert" : "status"}>{previewError?.id === selected.id ? previewError.message : "Loading document preview…"}</p>}
      <section className="review-box"><h3>Text extraction and review</h3><p>OCR reads visible text. Configured AI can suggest structured facts; suggestions remain unconfirmed until you review them.</p>{selected.can_edit && <button className="button" disabled={processing} onClick={()=>void processDocument(selected)}>{processing?"Processing…":selected.processing_status==="failed"?"Retry extraction":"Run OCR and extraction"}</button>}{extraction&&<><p>Status: <strong>{extraction.status}</strong> · engine: {extraction.engine_version}</p>{extraction.candidates.map((candidate,index)=><div className="field" key={index}><label>{candidate.field} · {Math.round(candidate.confidence*100)}% · page {candidate.source_page??"?"}</label><textarea disabled={!selected.can_edit} value={candidate.value} onChange={e=>setExtraction({...extraction,candidates:extraction.candidates.map((c,i)=>i===index?{...c,value:e.target.value}:c)})}/></div>)}{extraction.ocr_text&&<details><summary>OCR source text</summary><pre>{extraction.ocr_text}</pre></details>}{selected.can_edit && extraction.status==="needs_review"&&<div className="review-actions"><button className="button" onClick={()=>void confirmExtraction(selected)}>Confirm reviewed facts</button><button className="button button-secondary" onClick={()=>void rejectExtraction(selected)}>Reject suggestions</button></div>}</>}</section>
      {selected.can_edit && <button className="button button-danger" onClick={() => void remove(selected)}>Delete document</button>}
    </DocumentSheet>}
  </main>;
}
