/** Format an ISO datetime string as a date-only string (YYYY-MM-DD). */
export function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

/** Format an ISO datetime string as "YYYY-MM-DD HH:MM". */
export function formatDatetime(iso: string): string {
  return iso.slice(0, 16).replace("T", " ");
}
