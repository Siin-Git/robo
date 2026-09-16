"use client";

import { createContext, useContext } from "react";

export const SetupStyleContext = createContext<{
  risk: Record<string, string>;
  theme: Record<string, string>;
  review: Record<string, string>;
} | null>(null);

export function useSetupStyles() {
  const styles = useContext(SetupStyleContext);
  if (!styles) throw new Error("Setup pages require SetupStyleProvider.");
  return styles;
}
