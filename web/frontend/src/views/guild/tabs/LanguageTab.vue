<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { api } from "@/api/client";
import type { LanguageConfig } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useAutoSave } from "@/composables/useAutoSave";

const props = defineProps<{ guildId: string }>();

const config = ref<LanguageConfig | null>(null);
const loading = ref(true);
const { saving, error, success, ready } = useAutoSave(config, (c) =>
  api.put<LanguageConfig>(`/guilds/${props.guildId}/language`, { language: c.language }),
);

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

onMounted(async () => {
  try {
    config.value = await api.get<LanguageConfig>(`/guilds/${props.guildId}/language`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
    await nextTick();
    ready.value = true;
  }
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Language</h2>
      <p class="text-muted-foreground text-sm">
        Controls the language NerpyBot uses for all its responses in this server, including command replies, embeds, and
        automated messages. Changes are applied immediately and auto-save as soon as you make a selection.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="language-select">
          Language
          <InfoTooltip text="The locale NerpyBot will use when replying in this server (e.g. English, Deutsch)." />
        </label>
        <div class="flex items-center gap-3">
          <select
            id="language-select"
            v-model="config.language"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-48"
          >
            <option v-for="lang in LANGUAGES" :key="lang.code" :value="lang.code">
              {{ lang.label }}
            </option>
          </select>
          <span v-if="saving" class="text-xs text-muted-foreground">Saving…</span>
          <span v-else-if="success" class="text-xs text-green-400">✓ Saved</span>
        </div>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
