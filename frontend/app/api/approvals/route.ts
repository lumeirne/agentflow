/**
 * GET  /api/approvals        → list pending approvals
 * POST /api/approvals/[id]   → approve / reject  (handled in [id]/route.ts)
 */
import { auth0 } from "@/lib/auth0";
import { NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET() {
  try {
    const { token } = await auth0.getAccessToken();
    if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

    const res = await fetch(`${API_BASE}/api/approvals`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] GET /api/approvals error:", err);
    return NextResponse.json({ detail: "Failed to reach backend." }, { status: 502 });
  }
}
