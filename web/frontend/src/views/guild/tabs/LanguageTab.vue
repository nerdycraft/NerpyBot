<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { LanguageConfig } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const config = ref<LanguageConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref(false);

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
  }
});

async function save() {
  if (!config.value) return;
  saving.value = true;
  success.value = false;
  error.value = null;
  try {
    config.value = await api.put<LanguageConfig>(`/guilds/${props.guildId}/language`, {
      language: config.value.language,
    });
    success.value = true;
    setTimeout(() => (success.value = false), 3000);
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
      <p class="text-muted-foreground text-sm">Sets the bot's response language for this server.</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="language-select">Language</label>
        <select
          id="language-select"
          v-model="config.language"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-48"
        >
          <option v-for="lang in LANGUAGES" :key="lang.code" :value="lang.code">
            {{ lang.label }}
          </option>
        </select>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
      <p v-if="success" class="text-green-400 text-sm">Saved.</p>

      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors"
        :disabled="saving"
        @click="save"
      >
        {{ saving ? "Saving…" : "Save" }}
      </button>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
