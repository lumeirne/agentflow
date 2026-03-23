import { auth0 } from "@/lib/auth0";

export async function middleware(request: Request) {
  return await auth0.middleware(request);
}

export const config = {
  matcher: [
    // Auth routes handled by the SDK
    "/auth/:path*",
    // Protect API routes
    "/api/:path*",
  ],
};
