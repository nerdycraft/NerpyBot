<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { api } from "@/api/client";
import type { AutoKickerConfig } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useManualSave } from "@/composables/useManualSave";

const props = defineProps<{ guildId: string }>();

const config = ref<AutoKickerConfig | null>(null);
const loading = ref(true);
const { saving, error, success, dirty, ready, save } = useManualSave(config, async (c) => {
  if (!Number.isInteger(c.kick_after) || c.kick_after < 1) {
    throw new Error("Kick-after must be at least 1 day.");
  }
  return api.put<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`, {
    kick_after: c.kick_after,
    enabled: c.enabled,
    reminder_message: c.reminder_message,
  });
});

let _loadSeq = 0;

async function loadConfig() {
  const seq = ++_loadSeq;
  ready.value = false;
  loading.value = true;
  error.value = null;
  config.value = null;
  try {
    const next = await api.get<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`);
    if (seq !== _loadSeq) return;
    if (next.kick_after < 1) next.kick_after = 1;
    config.value = next;
  } catch (e: unknown) {
    if (seq !== _loadSeq) return;
    error.value = e instanceof Error ? e.message : "Failed to load";
  }
  if (seq !== _loadSeq) return;
  loading.value = false;
  await nextTick();
  ready.value = true;
}

watch(() => props.guildId, () => void loadConfig(), { immediate: true });
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Auto-Kicker</h2>
      <p class="text-muted-foreground text-sm">
        Automatically kicks members who have not verified or shown activity within a configurable number of days.
        The bot will send an optional reminder message before kicking if one is set.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium flex items-center gap-1.5">
          Enabled
          <InfoTooltip text="When disabled, no members will be kicked regardless of the other settings." />
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="kick-after">
          Kick after (days)
          <InfoTooltip text="Number of days of inactivity before a member is kicked. Must be at least 1." />
        </label>
        <input
          id="kick-after"
          v-model.number="config.kick_after"
          type="number"
          min="1"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-32"
        />
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="kick-reminder">
          Reminder message (optional)
          <InfoTooltip text="If set, NerpyBot will DM this message to the member before kicking them. Leave blank to kick silently." />
        </label>
        <textarea
          id="kick-reminder"
          v-model="config.reminder_message"
          rows="3"
          placeholder="You will be kicked soon due to inactivity…"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-full resize-y"
        />
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
      <div class="flex items-center gap-3">
        <button
          :disabled="!dirty || saving"
          class="px-4 py-1.5 text-sm font-medium rounded bg-primary text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          @click="save"
        >
          {{ saving ? "Saving…" : "Save" }}
        </button>
        <span v-if="success" class="text-xs text-green-400">✓ Saved</span>
      </div>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
