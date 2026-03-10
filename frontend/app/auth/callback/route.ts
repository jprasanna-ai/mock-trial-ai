import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

function sanitizeRedirectPath(raw: string): string {
  if (
    !raw.startsWith("/") ||
    raw.startsWith("//") ||
    raw.includes("\r") ||
    raw.includes("\n") ||
    raw.includes("%0")
  ) {
    return "/";
  }
  return raw;
}

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = sanitizeRedirectPath(searchParams.get("next") ?? "/");

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  return NextResponse.redirect(`${origin}/login?error=auth_failed`);
}
