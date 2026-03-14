/**
 * Fetches /api/legal/contact once at module scope and caches the result.
 * No auth required — the endpoint is public.
 * Leaves empty strings on fetch failure (graceful degradation).
 */
import { reactive } from "vue";

interface LegalContact {
  enabled: boolean;
  name: string;
  street: string;
  zip_city: string;
  country_en: string;
  country_de: string;
  email: string;
}

const contact = reactive<LegalContact>({
  enabled: false,
  name: "",
  street: "",
  zip_city: "",
  country_en: "",
  country_de: "",
  email: "",
});

let fetchPromise: Promise<void> | null = null;

export function useLegalContact() {
  if (!fetchPromise) {
    fetchPromise = fetch("/api/legal/contact")
      .then((res) => res.json())
      .then((data: LegalContact) => {
        Object.assign(contact, data);
      })
      .catch(() => {
        fetchPromise = null; // allow retry on next call
      });
  }
  return { contact };
}
