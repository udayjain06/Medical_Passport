import Link from "next/link";

export default function TermsPage() {
  return <main className="page-wrap"><p className="eyebrow">Terms</p><h1>Terms of use</h1><p><strong>REQUIRES LEGAL REVIEW</strong></p><p>This placeholder describes a personal health-record tool and does not replace professional medical advice. Eligibility, permitted use, service limits, liability, and dispute terms must be confirmed by qualified counsel before real users rely on these terms.</p><p><Link href="/signup">Return to signup</Link></p></main>;
}
