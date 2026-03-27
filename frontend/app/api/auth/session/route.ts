import { auth0 } from "@/lib/auth0";
import { NextResponse } from "next/server";

/**
 * GET /api/auth/session
 * Returns the current user session and access token for API calls
 */
export async function GET() {
  try {
    const session = await auth0.getSession();

    if (!session) {
      return NextResponse.json(null, { status: 401 });
    }

    const { token, expiresAt } = await auth0.getAccessToken();

    if (!token) {
      return NextResponse.json(null, { status: 401 });
    }

    return NextResponse.json({
      accessToken: token,
      accessTokenExpiresAt: expiresAt,
    });
  } catch (error) {
    console.error("Session error:", error);
    return NextResponse.json(null, { status: 401 });
  }
}
