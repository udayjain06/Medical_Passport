import Link from "next/link";

export default function TermsPage() {
  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">Terms</p>
        <h1>Terms of service</h1>
        <p><strong>REQUIRES LEGAL REVIEW</strong></p>
      </header>
      <section className="panel">
        <p>This placeholder is not a final agreement. The service owner must obtain legal review and publish approved terms before inviting real users.</p>
        <p>Medical Passport is a personal record tool and does not replace professional medical care.</p>
        <Link className="panel-link" href="/signup">Return to sign up</Link>
      </section>
    </main>
  );
}
