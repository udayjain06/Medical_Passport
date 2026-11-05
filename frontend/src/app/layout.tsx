import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Medical Passport — your health history, in one place",
  description: "A private, patient-controlled home for health information. Start with your profile and build a clearer medical history over time.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
