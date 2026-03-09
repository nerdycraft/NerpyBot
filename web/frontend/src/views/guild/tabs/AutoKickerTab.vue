<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { AutoKickerConfig } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const config = ref<AutoKickerConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref(false);

onMounted(async () => {
  try {
    config.value = await api.get<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`);
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
    config.value = await api.put<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`, {
      kick_after: config.value.kick_after,
      enabled: config.value.enabled,
      reminder_message: config.value.reminder_message,
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
      <h2 class="text-lg font-semibold">Auto-Kicker</h2>
      <p class="text-muted-foreground text-sm">Kick members who have been inactive for too long.</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium">Enabled</span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="kick-after">Kick after (days)</label>
        <input
          id="kick-after"
          v-model.number="config.kick_after"
          type="number"
          min="1"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-32"
        />
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="kick-reminder">Reminder message (optional)</label>
        <textarea
          id="kick-reminder"
          v-model="config.reminder_message"
          rows="3"
          placeholder="You will be kicked soon due to inactivity…"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-full resize-y"
        />
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
