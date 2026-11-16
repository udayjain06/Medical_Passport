import Link from "next/link";
import { ResetPasswordForm } from "@/components/reset-password-form";

type ResetPasswordPageProps = {
  searchParams: Promise<{ token?: string | string[] }>;
};

export default async function ResetPasswordPage({ searchParams }: ResetPasswordPageProps) {
  const params = await searchParams;
  const token = Array.isArray(params.token) ? params.token[0] ?? null : params.token ?? null;

  return (
    <>
      <header className="site-header">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span>Medical Passport</span>
        </Link>
        <Link className="text-button" href="/">Back to home</Link>
      </header>
      <main className="auth-wrap"><ResetPasswordForm token={token} /></main>
    </>
  );
}
