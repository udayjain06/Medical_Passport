"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";

export default function PrivacyPage() {
  const { language, t } = useLanguage();
  return (
    <main className="page-wrap">
      <header className="page-heading">
        <p className="eyebrow">{t("privacy")}</p>
        <h1>{t("privacyNotice")}</h1>
        <p><strong>{t("legalReview")}</strong></p>
      </header>
      <section className="panel">
        <p>{language === "hi" ? "यह अंतिम गोपनीयता सूचना नहीं है। वास्तविक उपयोगकर्ताओं को आमंत्रित करने से पहले सेवा स्वामी को समझाना होगा कि कौन-सा डेटा लिया जाता है, क्यों उपयोग होता है, कैसे सुरक्षित रखा जाता है और लोग अपने अधिकार कैसे इस्तेमाल कर सकते हैं।" : "This placeholder is not a final privacy notice. Before inviting real users, the service owner must explain what data is collected, why it is used, how it is protected, and how people can exercise their rights."}</p>
        <p>{language === "hi" ? "इस सूचना की समीक्षा तक कृत्रिम जानकारी का उपयोग करें।" : "Use synthetic information while this notice is under review."}</p>
        <Link className="panel-link" href="/signup">{language === "hi" ? "साइन अप पर लौटें" : "Return to sign up"}</Link>
      </section>
    </main>
  );
}
