import { defineConfig } from "@playwright/test";
import demo from "./playwright.demo.config";

// Generate ../.work/capstone_audit.json with scripts/verify_capstone.py first.
export default defineConfig({...demo, testMatch:["capstone.spec.ts", "capstone-audit.spec.ts"]});
