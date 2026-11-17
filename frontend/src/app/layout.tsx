import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LanguageProvider, type Language } from "@/lib/i18n";
import { PwaRegistration } from "@/components/pwa-registration";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medical Passport — your health history, in one place",
  description:
    "A private, patient-controlled home for health information. Start with your profile and build a clearer medical history over time.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icons/medical-passport.svg",
    apple: "/icons/medical-passport.svg",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Medical Passport",
  },
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const language: Language = (await cookies()).get("mp_language")?.value === "hi" ? "hi" : "en";
  return (
    <html lang={language}>
      <body>
        <LanguageProvider initialLanguage={language}>
          <PwaRegistration />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
