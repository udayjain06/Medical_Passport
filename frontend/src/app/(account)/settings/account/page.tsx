"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";

export default function AccountData() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function exportData() {
    setBusy(true);
    setError("");
    try {
      const data = await apiRequest<unknown>("/auth/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "medical-passport-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Export failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteAccount() {
    setBusy(true);
    setError("");
    try {
      await apiRequest("/auth/delete-account", { method: "POST", body: JSON.stringify({ password }) });
      router.replace("/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not delete the account.");
      setBusy(false);
    }
  }

  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">Your data, your control</p>
        <h1>Data &amp; privacy</h1>
        <p>Download a copy of your records or permanently erase your account.</p>
      </header>
      <section className="panel">
        <h2>Export my data</h2>
        <p>A JSON file with your profile, timeline, document list and emergency links. Document files are not included.</p>
        <button className="button" disabled={busy} onClick={() => void exportData()}>Download export</button>
      </section>
      <section className="panel" style={{ marginTop: 20 }}>
        <h2>Delete my account</h2>
        <p>This permanently erases your account, profiles you own, uploaded documents, timeline and emergency links. It cannot be undone.</p>
        <div className="field">
          <label htmlFor="del-pass">Password</label>
          <input id="del-pass" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="del-confirm">Type DELETE to confirm</label>
          <input id="del-confirm" value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-danger" disabled={busy || !password || confirmText !== "DELETE"} onClick={() => void deleteAccount()}>
          Delete account permanently
        </button>
      </section>
    </main>
  );
}
