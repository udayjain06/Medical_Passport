"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, apiRequest } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

type Variant = "card" | "compact" | "landing";

export function DemoLoginAction({ variant }: { variant: Variant }) {
  const router = useRouter();
  const { language } = useLanguage();
  const [available, setAvailable] = useState(false);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const hindi = language === "hi";

  useEffect(() => {
    let active = true;
    apiRequest<{ enabled: boolean }>("/auth/demo-status")
      .then((result) => {
        if (active) setAvailable(result.enabled);
      })
      .catch(() => {
        if (active) setAvailable(false);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function enterDemo() {
    setBusy(true);
    setError("");
    try {
      await apiRequest("/auth/demo-login", { method: "POST" });
      router.replace("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : hindi
            ? "डेमो अभी उपलब्ध नहीं है।"
            : "Demo access is unavailable right now.",
      );
      setBusy(false);
    }
  }

  if (checking || !available) return null;

  const button = (
    <button className="button demo-button" type="button" onClick={enterDemo} disabled={busy}>
      {busy
        ? hindi
          ? "डेमो खोला जा रहा है…"
          : "Opening demo…"
        : hindi
          ? "डेमो देखें →"
          : "Explore Demo →"}
    </button>
  );

  if (variant === "landing") return button;

  if (variant === "compact") {
    return (
      <div className="demo-compact">
        <p>{hindi ? "खाता बनाए बिना पहले देखना चाहते हैं?" : "Want to explore before creating an account?"}</p>
        {button}
        {error && <p className="form-error" role="alert">{error}</p>}
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
      {error && <p className="form-error" role="alert">{error}</p>}
      <p className="demo-disclaimer">
        {hindi
          ? "सभी जानकारी काल्पनिक है और नैदानिक उपयोग के लिए नहीं है।"
          : "All demo information is synthetic and not for clinical use."}
      </p>
    </section>
  );
}
