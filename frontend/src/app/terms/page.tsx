"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";

export default function TermsPage() {
  const { language, t } = useLanguage();
  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">{t("terms")}</p>
        <h1>{t("termsService")}</h1>
        <p><strong>{t("legalReview")}</strong></p>
      </header>
      <section className="panel">
        <p>{language === "hi" ? "यह अंतिम समझौता नहीं है। वास्तविक उपयोगकर्ताओं को आमंत्रित करने से पहले सेवा स्वामी को कानूनी समीक्षा कराकर स्वीकृत शर्तें प्रकाशित करनी होंगी।" : "This placeholder is not a final agreement. The service owner must obtain legal review and publish approved terms before inviting real users."}</p>
        <p>{language === "hi" ? "Medical Passport व्यक्तिगत रिकॉर्ड का साधन है और पेशेवर चिकित्सा देखभाल का विकल्प नहीं है।" : "Medical Passport is a personal record tool and does not replace professional medical care."}</p>
        <Link className="panel-link" href="/signup">{language === "hi" ? "साइन अप पर लौटें" : "Return to sign up"}</Link>
      </section>
    </main>
  );
}
