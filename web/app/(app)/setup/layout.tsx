import type { ReactNode } from "react";
import { SetupStyleProvider } from "./SetupStyleProvider";

// Keep shared onboarding styles owned by the persistent layout. Page navigation
// must not unmount a stylesheet that the adjacent page / CSS refresh still uses.
export default function SetupLayout({ children }: { children: ReactNode }) {
  return <SetupStyleProvider>{children}</SetupStyleProvider>;
}
