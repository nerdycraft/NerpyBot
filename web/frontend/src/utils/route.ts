import type { LocationQueryValue } from "vue-router";

/**
 * Normalises a Vue Router query value to a scalar string (or null/undefined).
 * Vue Router represents multi-value params as arrays; this returns the first element.
 */
export function toQueryScalar(
  v: LocationQueryValue | LocationQueryValue[] | undefined,
): string | null | undefined {
  return Array.isArray(v) ? v[0] : v;
}
