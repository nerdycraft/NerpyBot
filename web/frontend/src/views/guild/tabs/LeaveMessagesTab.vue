<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { api } from "@/api/client";
import type { LeaveMessageConfig } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useManualSave } from "@/composables/useManualSave";

const props = defineProps<{ guildId: string }>();

const config = ref<LeaveMessageConfig | null>(null);
const loading = ref(true);
const { saving, error, success, dirty, ready, save } = useManualSave(config, (c) =>
  api.put<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`, {
    channel_id: c.channel_id,
    message: c.message,
    enabled: c.enabled,
  }),
);

async function loadConfig() {
  ready.value = false;
  loading.value = true;
  error.value = null;
  config.value = null;
  try {
    config.value = await api.get<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
    await nextTick();
    ready.value = true;
  }
}

watch(() => props.guildId, () => void loadConfig(), { immediate: true });
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Leave Messages</h2>
      <p class="text-muted-foreground text-sm">
        Post a custom message to a channel whenever a member leaves or is removed from the server. Use
        <code class="font-mono text-xs">{user}</code> in the message text to mention the departing member by name.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium flex items-center gap-1.5">
          Enabled
          <InfoTooltip text="When enabled, the bot will post a leave message each time a member leaves or is removed from the server." />
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5">
          Channel
          <InfoTooltip text="The text channel where leave messages will be posted. The bot must have permission to send messages in this channel." />
        </label>
        <div class="w-64">
          <DiscordPicker
            :model-value="config.channel_id ?? ''"
            :guild-id="guildId"
            kind="channel"
            @update:model-value="config.channel_id = $event || null"
          />
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="leave-message">
          Message
          <InfoTooltip text="The message text to post when a member leaves. Use {user} as a placeholder — it will be replaced with the departing member's username." />
        </label>
        <textarea
          id="leave-message"
          v-model="config.message"
          rows="3"
          placeholder="Goodbye {user}!"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-full resize-y"
        />
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
      <div class="flex items-center gap-3">
        <button
          :disabled="!dirty || saving"
          class="px-4 py-1.5 text-sm font-medium rounded bg-primary text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          @click="save()"
        >
          {{ saving ? "Saving…" : "Save" }}
        </button>
        <span v-if="success" class="text-xs text-green-400">✓ Saved</span>
      </div>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
