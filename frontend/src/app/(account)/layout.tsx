import { Suspense } from "react";
import { AccountNav } from "@/components/account-nav";
import { requireSession } from "@/lib/session";

async function ProtectedAccount({ children }: Readonly<{ children: React.ReactNode }>) {
  await requireSession();
  return <><AccountNav />{children}</>;
}

export default function AccountLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <Suspense fallback={<main className="page-wrap"><p className="loading" role="status">Checking your session…</p></main>}><ProtectedAccount>{children}</ProtectedAccount></Suspense>;
}
