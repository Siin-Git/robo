"use client";
import { useQuery } from "@tanstack/react-query";
import { get } from "./client";
import { DEMO_MODE } from "./comparison";
import type { ExperimentStatus } from "./experiment";

export function useComparisonMode() {
  return useQuery({queryKey:["experiment-setup-status"], queryFn:()=>get<ExperimentStatus>("/api/v1/me/experiment"), enabled:DEMO_MODE});
}
