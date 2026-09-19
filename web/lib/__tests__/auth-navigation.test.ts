import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "../../middleware";
import { safeNext } from "../auth-navigation";

describe("authentication return paths", () => {
  it("preserves the selected onboarding step through the login redirect", () => {
    const response = middleware(new NextRequest("http://localhost:3000/setup/portfolio?step=themes&category=기술"));
    const location = new URL(response.headers.get("location")!, "http://localhost:3000");
    expect(location.pathname).toBe("/login");
    expect(safeNext(location.searchParams.get("next"))).toBe("/setup/portfolio?step=themes&category=%EA%B8%B0%EC%88%A0");
    expect(location.searchParams.has("step")).toBe(false);
  });
  it.each([null, "https://example.com", "//example.com", "/\\example.com", "/login?next=/login", "/api/v1/auth/me", "/signup", "javascript:alert(1)"])("rejects external or circular return paths: %s", next => {
    expect(safeNext(next)).toBe("/dashboard");
  });
  it("allows protected pages with their query and fragment", () => {
    expect(safeNext("/setup/portfolio?step=review#comparison")).toBe("/setup/portfolio?step=review#comparison");
  });
});
