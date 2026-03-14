import { defineStore } from "pinia";
import { ref, watch } from "vue";

export const SUPPORTED_LOCALES = ["en", "de"] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

function detectBrowserLocale(): SupportedLocale {
  const candidates = [...(navigator.languages ?? []), navigator.language].filter(Boolean);
  for (const lang of candidates) {
    const normalized = lang.split("-")[0]?.toLowerCase();
    if ((SUPPORTED_LOCALES as readonly string[]).includes(normalized ?? "")) {
      return normalized as SupportedLocale;
    }
  }
  return "en";
}

export const useLocaleStore = defineStore(
  "locale",
  () => {
    const current = ref<SupportedLocale>(detectBrowserLocale());

    function setLocale(lang: SupportedLocale) {
      current.value = lang;
    }

    watch(
      current,
      (lang) => {
        document.documentElement.lang = lang;
      },
      { immediate: true },
    );

    return { current, setLocale, supportedLocales: SUPPORTED_LOCALES };
  },
  { persist: true },
);
