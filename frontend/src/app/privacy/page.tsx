import Link from "next/link";

export default function PrivacyPage() {
  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">Privacy</p>
        <h1>Privacy notice</h1>
        <p><strong>REQUIRES LEGAL REVIEW</strong></p>
      </header>
      <section className="panel">
        <p>This placeholder is not a final privacy notice. Before inviting real users, the service owner must explain what data is collected, why it is used, how it is protected, and how people can exercise their rights.</p>
        <p>Use synthetic information while this notice is under review.</p>
        <Link className="panel-link" href="/signup">Return to sign up</Link>
      </section>
    </main>
  );
}
