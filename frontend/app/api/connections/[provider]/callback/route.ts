/**
 * GET /api/connections/[provider]/callback
 *
 * Auth0 redirects here after the user authenticates with a social provider.
 * This route:
 *   1. Completes the Auth0 code exchange
 *   2. Extracts the idp_sub from the id_token (provider's Auth0 ID)
 *   3. Calls the backend to verify and link the identity
 *   4. If state=run:<runId> is present, redirects back to the run page
 *      with ?connected=<provider>&resume=<runId> so the run page can
 *      auto-trigger the resume endpoint.
 *   5. Otherwise redirects to /connections with success indicator.
 */
import { NextRequest, NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8000";
const AUTH0_DOMAIN = process.env.AUTH0_DOMAIN || "";
const CLIENT_ID = process.env.AUTH0_CLIENT_ID || "";
const CLIENT_SECRET = process.env.AUTH0_CLIENT_SECRET || "";
const APP_BASE = process.env.AUTH0_BASE_URL || "http://localhost:3000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  const { provider } = await params;
  const { searchParams } = new URL(req.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");
  const stateParam = searchParams.get("state") || "";

  // Extract return_to_run_id from state param (format: "run:<runId>")
  let returnToRunId: string | null = null;
  if (stateParam.startsWith("run:")) {
    returnToRunId = stateParam.slice(4);
  }

  // ── Auth0 returned an error ───────────────────────────────────────────────
  if (error) {
    console.error(`[callback] Auth0 error for ${provider}:`, error, errorDescription);
    const dest = returnToRunId ? `/runs/${returnToRunId}` : "/connections";
    const redirectUrl = new URL(dest, req.url);
    redirectUrl.searchParams.set("error", errorDescription || error);
    return NextResponse.redirect(redirectUrl);
  }

  if (!code) {
    const dest = returnToRunId ? `/runs/${returnToRunId}` : "/connections";
    const redirectUrl = new URL(dest, req.url);
    redirectUrl.searchParams.set("error", "No authorization code returned by Auth0.");
    return NextResponse.redirect(redirectUrl);
  }

  let idpSub: string | undefined;
  try {
    const tokenResponse = await fetch(`https://${AUTH0_DOMAIN}/oauth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        code,
        redirect_uri: `${APP_BASE}/api/connections/${provider}/callback`,
      }).toString(),
    });

    if (tokenResponse.ok) {
      const exchanged = await tokenResponse.json();
      if (exchanged.id_token) {
        try {
          const payloadBase64 = exchanged.id_token.split(".")[1];
          let normalizedB64 = payloadBase64.replace(/-/g, "+").replace(/_/g, "/");
          while (normalizedB64.length % 4 !== 0) normalizedB64 += "=";
          const payload = JSON.parse(atob(normalizedB64));
          idpSub = payload.sub;
          console.log(`[callback] Extracted idp_sub for ${provider}:`, idpSub);
        } catch (e) {
          console.error("[callback] Failed to parse id_token", e);
        }
      }
    } else {
      console.error(`[callback] Code exchange failed: ${tokenResponse.status}`);
    }
  } catch (err) {
    console.error(`[callback] Code exchange error:`, err);
  }

  // ── Notify backend to verify and link identity ────────────────────────────
  let backendError: string | null = null;
  try {
    const { token: appToken } = await auth0.getAccessToken();
    if (appToken) {
      const backendResponse = await fetch(`${API_BASE}/api/connections/${provider}/callback`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${appToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ idp_sub: idpSub }),
      });

      if (!backendResponse.ok) {
        const errorData = await backendResponse.json().catch(() => ({}));
        backendError = errorData.detail || `Backend returned ${backendResponse.status}`;
        console.error("[callback] Backend connection error:", backendError);
      }
    }
  } catch (err) {
    console.error("[callback] Backend notification error:", err);
    backendError = String(err);
  }

  // ── Redirect ──────────────────────────────────────────────────────────────
  if (returnToRunId) {
    // Return to the originating run page; the run page will auto-trigger resume
    const redirectUrl = new URL(`/runs/${returnToRunId}`, req.url);
    redirectUrl.searchParams.set("connected", provider);
    redirectUrl.searchParams.set("resume", returnToRunId);
    if (backendError) {
      redirectUrl.searchParams.set("connection_warning", backendError);
    }
    return NextResponse.redirect(redirectUrl);
  }

  const redirectUrl = new URL("/connections", req.url);
  redirectUrl.searchParams.set("connected", provider);
  if (backendError) {
    redirectUrl.searchParams.set("warning", backendError);
  }
  return NextResponse.redirect(redirectUrl);
}
