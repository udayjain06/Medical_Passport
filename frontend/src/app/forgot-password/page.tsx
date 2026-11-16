import Link from "next/link";
import { ForgotPasswordForm } from "@/components/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <>
      <header className="site-header">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">+</span>
          <span>Medical Passport</span>
        </Link>
        <Link className="text-button" href="/">Back to home</Link>
      </header>
      <main className="auth-wrap"><ForgotPasswordForm /></main>
    </>
  );
}
