import { NextRequest, NextResponse } from "next/server";

const ALLOWED_IP = "24.49.252.230";

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;

  // Only protect /users and /[username] style pages (not /api)
  if (path.startsWith("/api")) {
    return NextResponse.next();
  }

  // Protect /users and any single-segment path that looks like a username page
  const isUsers = path === "/users" || path.startsWith("/users/");
  const isProfile =
    path !== "/" &&
    !path.startsWith("/api") &&
    !path.startsWith("/_next") &&
    path.split("/").filter(Boolean).length === 1;

  if (!isUsers && !isProfile) {
    return NextResponse.next();
  }

  const forwarded = req.headers.get("x-forwarded-for") || "";
  const real = req.headers.get("x-real-ip") || "";
  const ip = (forwarded.split(",")[0] || real || "").trim();

  if (ip !== ALLOWED_IP) {
    // Wrong IP → pure white page
    return new NextResponse("", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/users", "/users/:path*", "/((?!api|_next|favicon.ico).*)"],
};
