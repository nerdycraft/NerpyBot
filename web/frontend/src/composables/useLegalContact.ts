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

let fetched = false;

export function useLegalContact() {
  if (!fetched) {
    fetch("/api/legal/contact")
      .then((res) => res.json())
      .then((data: LegalContact) => {
        fetched = true;
        Object.assign(contact, data);
      })
      .catch(() => {
        // leave empty strings — page renders without contact data
      });
  }
  return { contact };
}
