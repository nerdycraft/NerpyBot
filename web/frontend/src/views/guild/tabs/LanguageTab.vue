<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { LanguageConfig } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const config = ref<LanguageConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref(false);
const mounted = ref(false);

let _saveTimer: ReturnType<typeof setTimeout> | null = null;
let _clearSuccessTimer: ReturnType<typeof setTimeout> | null = null;

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "de", label: "Deutsch" },
];

watch(config, () => {
  if (!mounted.value || !config.value || saving.value) return;
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => void autoSave(), 600);
}, { deep: true });

onUnmounted(() => {
  if (_saveTimer) clearTimeout(_saveTimer);
  if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
});

onMounted(async () => {
  try {
    config.value = await api.get<LanguageConfig>(`/guilds/${props.guildId}/language`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
    await nextTick();
    mounted.value = true;
  }
});

async function autoSave() {
  if (!config.value) return;
  saving.value = true;
  success.value = false;
  error.value = null;
  try {
    config.value = await api.put<LanguageConfig>(`/guilds/${props.guildId}/language`, {
      language: config.value.language,
    });
    success.value = true;
    if (_clearSuccessTimer) clearTimeout(_clearSuccessTimer);
    _clearSuccessTimer = setTimeout(() => (success.value = false), 2000);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to save";
  } finally {
    saving.value = false;
  }
}
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
          <span title="The locale NerpyBot will use when replying in this server (e.g. English, Deutsch)." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
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
