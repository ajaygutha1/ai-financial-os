import { NextResponse, type NextRequest } from "next/server";

const REFRESH_COOKIE_NAME = "finos_refresh_token";
const PROTECTED_PREFIXES = ["/dashboard", "/transactions"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (!isProtected) {
    return NextResponse.next();
  }

  // Runs server-side and can read the httpOnly cookie, but only checks for
  // its presence -- it isn't validated here. The real check is the backend's
  // JWT verification on every API call; this just avoids flashing protected
  // UI at signed-out visitors before that round-trip.
  const hasRefreshCookie = request.cookies.has(REFRESH_COOKIE_NAME);
  if (!hasRefreshCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/transactions/:path*"],
};
