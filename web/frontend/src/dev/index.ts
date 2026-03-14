/**
 * Test mode entry point.
 *
 * VITE_TEST_MODE is a compile-time constant — Vite replaces every occurrence
 * with the literal string "true" or "false" at build time.  When the value is
 * "false" (the default), dead-code elimination strips this entire module and
 * all of its imports from the production bundle.
 */

export const isTestMode = import.meta.env.VITE_TEST_MODE === "true";

export const TEST_GUILD_IDS = new Set([
  "999000000000000001",
  "999000000000000002",
  "999000000000000003",
  "999000000000000004",
]);

/** Returns true when the given API path should be intercepted by the mock layer. */
export function isTestRequest(path: string): boolean {
  for (const id of TEST_GUILD_IDS) {
    if (path.includes(id)) return true;
  }
  return path.startsWith("/operator/");
}

export { resolveTestRequest } from "./resolver";
