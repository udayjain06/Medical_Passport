import Link from "next/link";
import { AuthForm } from "@/components/auth-form";

export default function SignupPage() {
  return <><header className="site-header"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">+</span><span>Medical Passport</span></Link><Link className="text-button" href="/">Back to home</Link></header><AuthForm mode="signup" /></>;
}
