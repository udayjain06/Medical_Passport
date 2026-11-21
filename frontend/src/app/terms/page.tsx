"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/language";

export default function TermsPage() {
  const { t } = useLanguage();
  return <main className="page-wrap"><p className="eyebrow">{t("Terms")}</p><h1>{t("Terms of use")}</h1><p><strong>REQUIRES LEGAL REVIEW</strong></p><p>This placeholder describes a personal health-record tool and does not replace professional medical advice. Eligibility, permitted use, service limits, liability, and dispute terms must be confirmed by qualified counsel before real users rely on these terms.</p><p><Link href="/signup">{t("Return to signup")}</Link></p></main>;
}
