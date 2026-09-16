"use client";

import type { ReactNode } from "react";
import risk from "./portfolio/risk-selection.module.css";
import theme from "./portfolio/theme-selection.module.css";
import review from "./portfolio/review.module.css";
import { SetupStyleContext } from "./style-context";

// Only this persistent layout component imports the CSS. Child pages consume
// the class names without emitting duplicate, page-owned stylesheet links.
export function SetupStyleProvider({ children }: { children: ReactNode }) {
  return <SetupStyleContext.Provider value={{ risk, theme, review }}>{children}</SetupStyleContext.Provider>;
}
