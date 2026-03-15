/**
 * Lazily fetches /api/legal/contact on the first call to useLegalContact() and
 * caches the result in the module-level fetchPromise / contact reactive state.
 * Subsequent calls return the same reactive contact without re-fetching.
 * No auth required — the endpoint is public.
 * Leaves all fields as empty strings and enabled as false on fetch failure
 * (graceful degradation); clears fetchPromise so the next call retries.
 */
import { computed, reactive } from "vue";

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

const isContactAvailable = computed(
  () => contact.enabled && !!contact.name && !!contact.street && !!contact.zip_city && !!contact.email,
);

let fetchPromise: Promise<void> | null = null;

export function useLegalContact() {
  if (!fetchPromise) {
    fetchPromise = fetch("/api/legal/contact")
      .then((res) => {
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
      })
      .then((data: LegalContact) => {
        Object.assign(contact, {
          enabled: Boolean(data.enabled),
          name: String(data.name ?? ""),
          street: String(data.street ?? ""),
          zip_city: String(data.zip_city ?? ""),
          country_en: String(data.country_en ?? ""),
          country_de: String(data.country_de ?? ""),
          email: String(data.email ?? ""),
        });
      })
      .catch(() => {
        fetchPromise = null; // allow retry on next call
      });
  }
  return { contact, isContactAvailable };
}
