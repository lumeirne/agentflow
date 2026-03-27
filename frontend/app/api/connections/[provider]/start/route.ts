/**
 * POST /api/connections/[provider]/start
 * Server-side proxy → backend POST /api/connections/{provider}/start
 *
 * Accepts optional body: { return_to_run_id?: string }
 * When return_to_run_id is provided it is forwarded to the backend so the
 * Auth0 authorize URL embeds it in the `state` param, allowing the callback
 * to redirect back to the originating run page.
 */
import { auth0 } from "@/lib/auth0";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  try {
    const { provider } = await params;

    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    // Forward any body (e.g. return_to_run_id) to the backend
    let body: Record<string, unknown> = {};
    try {
      body = await req.json();
    } catch {
      // No body or non-JSON — fine
    }

    const res = await fetch(`${API_BASE}/api/connections/${provider}/start`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error(`[proxy] POST /api/connections/[provider]/start error:`, err);
    return NextResponse.json(
      { error: "Failed to reach backend. Make sure the backend server is running at localhost:8000." },
      { status: 502 }
    );
  }
}
