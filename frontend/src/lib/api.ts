export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function responseMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (!item || typeof item !== "object") return "";
        const issue = item as { loc?: unknown[]; msg?: string };
        const field = issue.loc?.filter((part) => typeof part === "string").slice(-1)[0];
        return `${field ? `${field}: ` : ""}${issue.msg ?? "Invalid value"}`;
      }).filter(Boolean).join(" ");
    }
  }
  return status >= 500 ? "The service is unavailable. Please try again shortly." : "The request could not be completed.";
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (typeof window !== "undefined") {
    const profileId = window.sessionStorage.getItem("active_patient_profile");
    if (profileId && !headers.has("X-Patient-Profile")) headers.set("X-Patient-Profile", profileId);
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  try {
    return await fetch(`/api${path}`, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
      headers,
    });
  } catch {
    throw new ApiError("Could not reach Medical Passport. Check that the API is running.", 0);
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init);
  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(responseMessage(payload, response.status), response.status);
  return payload as T;
}
