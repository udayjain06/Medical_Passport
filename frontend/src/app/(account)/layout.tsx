import { Suspense } from "react";
import { AccountNav } from "@/components/account-nav";
import { EmailVerificationBanner } from "@/components/email-verification-banner";
import { requireSession } from "@/lib/session";

async function ProtectedAccount({ children }: Readonly<{ children: React.ReactNode }>) {
  const user = await requireSession();
  return <><AccountNav /><EmailVerificationBanner verified={Boolean(user.email_verified_at)} />{children}</>;
}

export default function AccountLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <Suspense fallback={<main className="page-wrap"><p className="loading" role="status">Checking your session…</p></main>}><ProtectedAccount>{children}</ProtectedAccount></Suspense>;
}
