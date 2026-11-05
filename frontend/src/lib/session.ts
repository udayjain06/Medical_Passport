import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export async function requireSession(): Promise<void> {
  const session = (await cookies()).get("mp_session")?.value;
  if (!session) redirect("/login");

  const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${apiOrigin}/api/auth/me`, {
      headers: { Cookie: `mp_session=${session}` },
      cache: "no-store",
    });
  } catch {
    throw new Error("The Medical Passport API is unavailable. Please try again shortly.");
  }
  if (!response.ok) redirect("/login");
}
