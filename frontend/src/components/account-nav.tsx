"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { apiRequest, ApiError } from "@/lib/api";
import { ProfileSwitcher } from "@/components/profile-switcher";

export function AccountNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function logout() {
    setBusy(true);
    setError("");
    try {
      await apiRequest<void>("/auth/logout", { method: "POST" });
      router.replace("/");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not log out. Please try again.");
      setBusy(false);
    }
  }

  return <div className="account-header" style={{ backdropFilter: "blur(20px) saturate(180%)", WebkitBackdropFilter: "blur(20px) saturate(180%)" }}>
    <header className="site-header">
      <Link className="brand" href="/dashboard"><span className="brand-mark" aria-hidden="true">+</span><span>Medical Passport</span></Link>
      <div className="account-actions">
        <ProfileSwitcher />
        <nav className="account-nav" aria-label="Account navigation"><Link href="/dashboard" aria-current={pathname === "/dashboard" ? "page" : undefined}>Overview</Link><Link href="/documents" aria-current={pathname.startsWith("/documents") ? "page" : undefined}>Documents</Link><Link href="/timeline" aria-current={pathname.startsWith("/timeline") ? "page" : undefined}>Timeline</Link><Link href="/emergency" aria-current={pathname.startsWith("/emergency") ? "page" : undefined}>Emergency</Link><Link href="/family" aria-current={pathname.startsWith("/family") ? "page" : undefined}>Family</Link><Link href="/settings/abha" aria-current={pathname.startsWith("/settings") ? "page" : undefined}>ABHA</Link><Link href="/profile" aria-current={pathname === "/profile" ? "page" : undefined}>My profile</Link></nav>
        <button className="text-button" type="button" onClick={logout} disabled={busy}>{busy ? "Logging out…" : "Log out"}</button>
      </div>
    </header>
    {error && <p className="form-error" role="alert" style={{ width: "min(1120px, calc(100% - 40px))", margin: "0 auto 10px" }}>{error}</p>}
  </div>;
}
