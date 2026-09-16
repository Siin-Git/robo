import { describe, expect, it, vi, beforeEach } from "vitest";
import { ApiError, api } from "@/lib/api/client";

function mockFetchOnce(status: number, body: unknown, headers: Record<string, string> = {}) {
  const h = new Headers({ "X-Request-ID": "req-1", ...headers });
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    headers: h,
    json: async () => body,
  }) as unknown as typeof fetch;
}

describe("api client", () => {
  beforeEach(() => {
    document.cookie = "ra_csrf=test-csrf-token";
  });

  it("parses error envelope", async () => {
    mockFetchOnce(403, { error: { code: "CSRF_INVALID", message: "bad", details: {} } });
    await expect(api("/api/v1/me/views", { method: "POST", body: "{}" })).rejects.toMatchObject({
      code: "CSRF_INVALID",
      status: 403,
    } as Partial<ApiError>);
  });

  it("attaches CSRF header on mutations only", async () => {
    mockFetchOnce(200, { ok: true });
    await api("/api/v1/me/views", { method: "POST", body: "{}" });
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [
      string,
      RequestInit & { headers: Record<string, string> },
    ];
    expect(init.headers["X-CSRF-Token"]).toBe("test-csrf-token");
  });

  it("does not attach CSRF header on GET", async () => {
    mockFetchOnce(200, { ok: true });
    await api("/api/v1/me/views");
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [
      string,
      RequestInit & { headers: Record<string, string> },
    ];
    expect(init.headers["X-CSRF-Token"]).toBeUndefined();
  });
});
