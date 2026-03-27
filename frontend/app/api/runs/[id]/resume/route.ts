/**
 * POST /api/runs/[id]/resume
 * Proxy → backend POST /api/runs/{id}/resume
 *
 * Called after a provider connection is restored to retry the failed step
 * and continue the run without a full restart.
 */
import { auth0 } from "@/lib/auth0";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    const res = await fetch(`${API_BASE}/api/runs/${id}/resume`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] POST /api/runs/[id]/resume error:", err);
    return NextResponse.json({ error: "Failed to reach backend." }, { status: 502 });
  }
}
