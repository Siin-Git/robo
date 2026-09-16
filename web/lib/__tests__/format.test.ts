import { describe, expect, it } from "vitest";
import { fmtActivePp, fmtDate, fmtNav, fmtPct, fmtReturn } from "@/lib/format";

describe("formatters", () => {
  it("formats percents", () => {
    expect(fmtPct(0.2663)).toBe("26.63%");
    expect(fmtPct(null)).toBe("—");
    expect(fmtPct(undefined)).toBe("—");
  });
  it("formats active weights with pp suffix and sign", () => {
    expect(fmtActivePp(0.075)).toBe("+7.50%p");
    expect(fmtActivePp(-0.0321)).toBe("-3.21%p");
    expect(fmtActivePp(null)).toBe("—");
  });
  it("formats returns with sign", () => {
    expect(fmtReturn(0.0214)).toBe("+2.14%");
    expect(fmtReturn(-0.0082)).toBe("-0.82%");
  });
  it("formats NAV", () => {
    expect(fmtNav(103.424)).toBe("103.42");
    expect(fmtNav(null)).toBe("—");
  });
  it("formats dates as YYYY.MM.DD", () => {
    expect(fmtDate("2026-09-14")).toBe("2026.09.14");
    expect(fmtDate(null)).toBe("—");
  });
});
