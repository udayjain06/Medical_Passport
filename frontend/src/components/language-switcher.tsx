"use client";

import { useLanguage } from "@/lib/language";

export function LanguageSwitcher() {
  const { language, setLanguage, t } = useLanguage();
  return <label className="language-control">{t("Language")} <select aria-label={t("Language")} value={language} onChange={(event) => setLanguage(event.target.value as "en" | "hi")}><option value="en">{t("English")}</option><option value="hi">{t("Hindi")}</option></select></label>;
}
