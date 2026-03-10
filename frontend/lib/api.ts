import { createClient } from "@/lib/supabase/client";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      return {
        "Content-Type": "application/json",
        Authorization: `Bearer ${data.session.access_token}`,
      };
    }
  } catch {
    // Auth not available
  }
  return { "Content-Type": "application/json" };
}

/**
 * Authenticated fetch wrapper. Automatically attaches the Supabase JWT
 * as a Bearer token so the backend can identify the user.
 */
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const authHeaders = await getAuthHeaders();
  const merged: HeadersInit = { ...authHeaders };

  if (options.headers) {
    const extra =
      options.headers instanceof Headers
        ? Object.fromEntries(options.headers.entries())
        : Array.isArray(options.headers)
          ? Object.fromEntries(options.headers)
          : options.headers;
    Object.assign(merged, extra);
  }

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (options.body instanceof FormData) {
    delete (merged as Record<string, string>)["Content-Type"];
  }

  return fetch(url, { ...options, headers: merged });
}
