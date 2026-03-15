<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { api } from "@/api/client";
import type { LanguageConfig } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useAutoSave } from "@/composables/useAutoSave";
import { type I18nKey, useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();
const { t } = useI18n();

const config = ref<LanguageConfig | null>(null);
const loading = ref(true);
const { saving, error, success, ready } = useAutoSave(config, (c) =>
  api.put<LanguageConfig>(`/guilds/${props.guildId}/language`, { language: c.language }),
);

const LANGUAGES: { code: string; labelKey: I18nKey }[] = [
  { code: "en", labelKey: "tabs.language.en" },
  { code: "de", labelKey: "tabs.language.de" },
];

async function loadConfig() {
  ready.value = false;
  loading.value = true;
  config.value = null;
  try {
    config.value = await api.get<LanguageConfig>(`/guilds/${props.guildId}/language`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
    await nextTick();
    ready.value = true;
  }
}

watch(
  () => props.guildId,
  () => void loadConfig(),
  { immediate: true },
);
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.language.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.language.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>

    <div v-else-if="config" class="space-y-4">
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="language-select">
          {{ t("tabs.language.label") }}
          <InfoTooltip :text="t('tabs.language.tooltip')" />
        </label>
        <div class="flex items-center gap-3">
          <select
            id="language-select"
            v-model="config.language"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-48"
          >
            <option v-for="lang in LANGUAGES" :key="lang.code" :value="lang.code">
              {{ t(lang.labelKey) }}
            </option>
          </select>
          <span v-if="saving" class="text-xs text-muted-foreground">{{ t("common.saving") }}</span>
          <span v-else-if="success" class="text-xs text-green-400">{{ t("common.saved") }}</span>
        </div>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
