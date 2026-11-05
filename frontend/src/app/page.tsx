import Link from "next/link";

function Brand() {
  return <Link className="brand" href="/" aria-label="Medical Passport home"><span className="brand-mark" aria-hidden="true">+</span><span>Medical Passport</span></Link>;
}

export default function Home() {
  return <>
    <header className="site-header">
      <Brand />
      <nav className="nav-links" aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#privacy">Privacy</a></nav>
      <div className="nav-actions"><Link className="button button-secondary button-small" href="/login">Log in</Link><Link className="button button-small" href="/signup">Create account</Link></div>
    </header>
    <main className="landing-main">
      <section className="hero" aria-labelledby="hero-title">
        <div>
          <p className="eyebrow">Your health, clearly kept</p>
          <h1 id="hero-title">When you cannot speak, your history should <em>speak for you.</em></h1>
          <p className="hero-copy">A private place to begin bringing your health information together. Start with a patient-reported profile; add records and review them as Medical Passport grows.</p>
          <div className="hero-actions"><Link className="button" href="/signup">Create your profile <span aria-hidden="true">→</span></Link><Link className="button button-secondary" href="/login">I already have an account</Link></div>
          <p className="trust-note">Your profile stays private behind your account. Emergency links are consent-based, limited, and expiring.</p>
        </div>
        <div className="hero-art" aria-hidden="true"><div className="sun-disc" /><div className="art-leaf" /><div className="record-sheet"><div className="record-top"><span className="record-badge">✳</span><span className="status-pill">Your profile</span></div><div className="record-line short" /><div className="record-line" /><div className="record-row"><span className="record-dot" /><span className="record-line" /></div><div className="record-row"><span className="record-dot" /><span className="record-line" /></div><div className="record-line short" /><div className="record-stamp">PATIENT<br />REPORTED</div></div></div>
      </section>
      <section className="section" id="how-it-works">
        <div className="section-heading"><p className="eyebrow">Built around your choices</p><h2>A clearer health story, one step at a time.</h2><p>Medical Passport complements India’s ABHA/ABDM ecosystem. It does not replace it.</p></div>
        <div className="feature-grid">
          <article className="feature-card"><span className="feature-symbol" aria-hidden="true">◌</span><h3>Start with what you know</h3><p>Keep your profile details together and mark them as patient-reported.</p></article>
          <article className="feature-card"><span className="feature-symbol" aria-hidden="true">⌕</span><h3>Review before it becomes history</h3><p>Upload a record, extract visible text with local OCR, edit the source-linked candidates, then confirm them into your timeline. AI structured suggestions need an explicitly configured provider.</p><span className="feature-status">OCR and human review available</span></article>
          <article className="feature-card" id="privacy"><span className="feature-symbol" aria-hidden="true">◇</span><h3>Sharing should be deliberate</h3><p>Create an expiring QR for selected emergency fields, then revoke it whenever you choose. Anyone with the link can view the selected information.</p><span className="feature-status">Consent-controlled QR available</span></article>
        </div>
      </section>
    </main>
    <footer className="footer">Medical Passport is a personal record tool, not a substitute for professional medical advice.</footer>
  </>;
}
