/**
 * GET /api/github/repos
 * Server-side proxy → backend /api/github/repos
 */
import { auth0 } from "@/lib/auth0";
import { NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function GET() {
  try {
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    const res = await fetch(`${API_BASE}/api/github/repos`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] GET /api/github/repos error:", err);
    return NextResponse.json(
      { detail: "Failed to reach backend. Make sure the backend is running." },
      { status: 502 }
    );
  }
}
