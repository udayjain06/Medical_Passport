import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LanguageProvider, type Language } from "@/lib/language";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medical Passport — your health history, in one place",
  description: "A private, patient-controlled home for health information. Start with your profile and build a clearer medical history over time.",
  manifest: "/manifest.webmanifest",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const savedLanguage = (await cookies()).get("mp_language")?.value;
  const language: Language = savedLanguage === "hi" ? "hi" : "en";
  return <html lang={language}><body><LanguageProvider initialLanguage={language}>{children}</LanguageProvider></body></html>;
}
