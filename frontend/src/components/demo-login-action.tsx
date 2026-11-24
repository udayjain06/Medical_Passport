"use client";

import Link from "next/link";
import { useLanguage } from "@/lib/i18n";

type Variant = "card" | "compact" | "landing";

export function DemoLoginAction({ variant }: { variant: Variant }) {
  const { language } = useLanguage();
  const hindi = language === "hi";

  const button = (
    <Link className="button demo-button" href="/demo">
      {hindi ? "डेमो देखें →" : "Explore Demo →"}
    </Link>
  );

  if (variant === "landing") return button;

  if (variant === "compact") {
    return (
      <div className="demo-compact">
        <p>{hindi ? "खाता बनाए बिना पहले देखना चाहते हैं?" : "Want to explore before creating an account?"}</p>
        {button}
      </div>
    );
  }

  return (
    <section className="panel demo-card" aria-labelledby="demo-card-title">
      <p className="eyebrow">{hindi ? "केवल काल्पनिक डेटा" : "Fictional data only"}</p>
      <h2 id="demo-card-title">
        {hindi ? "खाता बनाने से पहले देखना चाहते हैं?" : "Want to explore before creating an account?"}
      </h2>
      <p>
        {hindi
          ? "पूरा काल्पनिक रोगी प्रोफ़ाइल देखें। बिना पंजीकरण के मेडिकल रिकॉर्ड, रिपोर्ट, स्वास्थ्य समयरेखा और आपातकालीन QR आज़माएँ।"
          : "Experience Medical Passport with a complete preloaded fictional patient profile. Explore medical records, reports, health timeline and emergency QR without registration."}
      </p>
      {button}
      <p className="demo-disclaimer">
        {hindi
          ? "सभी जानकारी काल्पनिक है और नैदानिक उपयोग के लिए नहीं है।"
          : "All demo information is synthetic and not for clinical use."}
      </p>
    </section>
  );
}
