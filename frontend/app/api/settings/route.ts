/**
 * GET  /api/settings   → fetch user settings
 * POST /api/settings   → save user settings
 */
import { auth0 } from "@/lib/auth0";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET() {
  try {
    const { token } = await auth0.getAccessToken();
    if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

    const res = await fetch(`${API_BASE}/api/settings`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] GET /api/settings error:", err);
    return NextResponse.json({ detail: "Failed to reach backend." }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const { token } = await auth0.getAccessToken();
    if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

    const body = await req.json().catch(() => ({}));
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] POST /api/settings error:", err);
    return NextResponse.json({ detail: "Failed to reach backend." }, { status: 502 });
  }
}
