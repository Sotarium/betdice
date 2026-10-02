import { NextRequest, NextResponse } from "next/server";

const ALLOWED_IP = "24.49.252.230";

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;

  // Never block API or static
  if (
    path.startsWith("/api") ||
    path.startsWith("/_next") ||
    path === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  // Protect /users and profile pages (single segment)
  const segments = path.split("/").filter(Boolean);
  const isUsers = path === "/users" || path.startsWith("/users/");
  const isProfile = segments.length === 1 && segments[0] !== "";

  if (!isUsers && !isProfile) {
    return NextResponse.next();
  }

  const forwarded = req.headers.get("x-forwarded-for") || "";
  const real = req.headers.get("x-real-ip") || "";
  const ip = (forwarded.split(",")[0] || real || "").trim();

  if (ip !== ALLOWED_IP) {
    return new NextResponse("", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
