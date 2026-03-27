/**
 * GET  /api/runs        → list runs
 * POST /api/runs        → create run
 */
import { auth0 } from "@/lib/auth0";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

async function getToken() {
  const { token } = await auth0.getAccessToken();
  return token;
}

export async function GET() {
  try {
    const token = await getToken();
    if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

    const res = await fetch(`${API_BASE}/api/runs`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] GET /api/runs error:", err);
    return NextResponse.json({ detail: "Failed to reach backend." }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const token = await getToken();
    if (!token) return NextResponse.json({ error: "Not authenticated" }, { status: 401 });

    const body = await req.json().catch(() => ({}));
    const res = await fetch(`${API_BASE}/api/runs`, {
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
    console.error("[proxy] POST /api/runs error:", err);
    return NextResponse.json({ detail: "Failed to reach backend." }, { status: 502 });
  }
}
