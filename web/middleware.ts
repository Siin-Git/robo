import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/signup"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (process.env.NEXT_PUBLIC_CAPSTONE_DEMO === "1") {
    if (pathname === "/signup") return NextResponse.redirect(new URL("/login", req.url));
    if (["/setup", "/views", "/performance", "/portfolio"].some(p => pathname === p || pathname.startsWith(p + "/"))) {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
  }
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next();
  }
  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }
  const session = req.cookies.get("ra_session")?.value;
  if (!session) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  // NOTE: page-level admin gating is enforced server-side by the API (403);
  // the admin sidebar entry is hidden client-side via /auth/me role.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
