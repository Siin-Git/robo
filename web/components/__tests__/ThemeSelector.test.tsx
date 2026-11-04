import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ThemeSelector } from "@/components/views/ThemeSelector";
import type { Theme } from "@/lib/api/types";

const THEMES: Theme[] = [
  { theme_id: "ai", display_name: "AI", theme_type: "theme", ticker: "AIQ",
    active: true, universe_version: "V0.1", inactive_reason: null },
  { theme_id: "semiconductor", display_name: "Semi", theme_type: "sector", ticker: "SOXX",
    active: true, universe_version: "V0.1", inactive_reason: null },
  { theme_id: "optical_networking", display_name: "Optical", theme_type: "theme", ticker: null,
    active: false, universe_version: "V0.1", inactive_reason: "no proxy" },
];

describe("ThemeSelector", () => {
  it("selects up to max themes and blocks inactive", () => {
    const onToggle = vi.fn();
    render(<ThemeSelector themes={THEMES} selected={["ai", "semiconductor"]} onToggle={onToggle} />);
    expect(screen.getByText("선택 2/2")).toBeInTheDocument();
    const optical = screen.getByRole("button", { name: /광네트워크/ });
    expect(optical).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /^AI/ }));
    expect(onToggle).toHaveBeenCalledWith("ai");
  });

  it("shows 준비 중 badge for inactive themes", () => {
    render(<ThemeSelector themes={THEMES} selected={[]} onToggle={() => {}} />);
    const badges = screen.getAllByText("준비 중");
    expect(badges.length).toBeGreaterThanOrEqual(1);
    expect(badges.some((b) => b.tagName === "SPAN")).toBe(true);
  });
});
