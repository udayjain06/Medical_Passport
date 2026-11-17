import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LanguageProvider, type Language } from "@/lib/i18n";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medical Passport — your health history, in one place",
  description: "A private, patient-controlled home for health information. Start with your profile and build a clearer medical history over time.",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const language: Language = (await cookies()).get("mp_language")?.value === "hi" ? "hi" : "en";
  return <html lang={language}><body><LanguageProvider initialLanguage={language}>{children}</LanguageProvider></body></html>;
}
