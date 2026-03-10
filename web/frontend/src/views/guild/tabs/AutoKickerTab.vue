<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { api } from "@/api/client";
import type { AutoKickerConfig } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useAutoSave } from "@/composables/useAutoSave";

const props = defineProps<{ guildId: string }>();

const config = ref<AutoKickerConfig | null>(null);
const loading = ref(true);
const { saving, error, success, ready } = useAutoSave(config, (c) =>
  api.put<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`, {
    kick_after: c.kick_after,
    enabled: c.enabled,
    reminder_message: c.reminder_message,
  }),
);

onMounted(async () => {
  try {
    config.value = await api.get<AutoKickerConfig>(`/guilds/${props.guildId}/auto-kicker`);
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
      <h2 class="text-lg font-semibold">Auto-Kicker</h2>
      <p class="text-muted-foreground text-sm">
        Automatically kicks members who have not verified or shown activity within a configurable number of days.
        Changes auto-save as you type; the bot will send an optional reminder message before kicking if one is set.
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
      <p v-if="saving" class="text-xs text-muted-foreground">Saving…</p>
      <p v-else-if="success" class="text-xs text-green-400">✓ Saved</p>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
