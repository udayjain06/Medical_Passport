"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/language";

export default function PrivacyPage() {
  const { t } = useLanguage();
  return <main className="page-wrap"><p className="eyebrow">{t("Privacy")}</p><h1>{t("Privacy notice")}</h1><p><strong>REQUIRES LEGAL REVIEW</strong></p><p>This placeholder explains that Medical Passport stores account and health information to provide the features you choose. Review, retention, sharing, deletion, and applicable privacy rights must be confirmed by qualified counsel before real users rely on this notice.</p><p><Link href="/signup">{t("Return to signup")}</Link></p></main>;
}
