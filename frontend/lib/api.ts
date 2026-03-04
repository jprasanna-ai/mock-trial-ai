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
