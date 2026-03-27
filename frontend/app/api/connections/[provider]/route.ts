/**
 * DELETE /api/connections/[provider]
 * Server-side proxy → backend DELETE /api/connections/{provider}
 */
import { auth0 } from "@/lib/auth0";
import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  try {
    const { provider } = await params;
    const { token } = await auth0.getAccessToken();
    if (!token) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    const res = await fetch(`${API_BASE}/api/connections/${provider}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("[proxy] DELETE /api/connections/[provider] error:", err);
    return NextResponse.json(
      { error: "Failed to reach backend" },
      { status: 502 }
    );
  }
}

