<script setup lang="ts">
import { useLocaleStore, type SupportedLocale } from "@/stores/locale";
import { useI18n } from "@/i18n";

const locale = useLocaleStore();
const { t } = useI18n();

const LABELS: Record<SupportedLocale, string> = {
  en: "EN",
  de: "DE",
};
</script>

<template>
  <select
    :value="locale.current"
    class="bg-transparent border border-border rounded px-1.5 py-0.5 text-xs text-muted-foreground cursor-pointer hover:border-primary transition-colors"
    :aria-label="t('language_switcher.aria_label', { lang: locale.current.toUpperCase() })"
    @change="locale.setLocale(($event.target as HTMLSelectElement).value as SupportedLocale)"
  >
    <option v-for="lang in locale.supportedLocales" :key="lang" :value="lang">
      {{ LABELS[lang] }}
    </option>
  </select>
</template>
