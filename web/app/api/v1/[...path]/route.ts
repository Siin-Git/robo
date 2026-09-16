import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.FASTAPI_INTERNAL_URL ?? "http://127.0.0.1:8000";

async function proxy(req: NextRequest, params: { path?: string[] }) {
  const target = `${BACKEND}/api/v1/${(params.path ?? []).join("/")}${req.nextUrl.search}`;
  const headers = new Headers();
  const cookie = req.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  const csrf = req.headers.get("x-csrf-token");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const init: RequestInit & { duplex?: "half" } = { method: req.method, headers, redirect: "manual" };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.arrayBuffer();
    init.duplex = "half";
  }
  let upstream: Response;
  try {
    upstream = await fetch(target, init as RequestInit);
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_UNAVAILABLE", message: "Backend is unreachable.", details: {} } },
      { status: 503 },
    );
  }
  const body = await upstream.arrayBuffer();
  const res = new NextResponse(body, { status: upstream.status });
  // Set-Cookie must be forwarded one-by-one (Headers.forEach would merge
  // multiple cookies into a single invalid header).
  const getSetCookie = (upstream.headers as Headers & { getSetCookie?: () => string[] })
    .getSetCookie;
  if (typeof getSetCookie === "function") {
    for (const value of getSetCookie.call(upstream.headers)) {
      res.headers.append("set-cookie", value);
    }
  } else {
    const single = upstream.headers.get("set-cookie");
    if (single) res.headers.append("set-cookie", single);
  }
  upstream.headers.forEach((value, key) => {
    if (["x-request-id", "content-type"].includes(key.toLowerCase())) {
      res.headers.append(key, value);
    }
  });
  return res;
}

export async function GET(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return proxy(req, ctx.params);
}
export async function POST(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return proxy(req, ctx.params);
}
export async function PUT(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return proxy(req, ctx.params);
}
export async function PATCH(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return proxy(req, ctx.params);
}
export async function DELETE(req: NextRequest, ctx: { params: { path?: string[] } }) {
  return proxy(req, ctx.params);
}
