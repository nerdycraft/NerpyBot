<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { LeaveMessageConfig } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";

const props = defineProps<{ guildId: string }>();

const config = ref<LeaveMessageConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref(false);
const mounted = ref(false);

let _saveTimer: ReturnType<typeof setTimeout> | null = null;
let _clearSuccessTimer: ReturnType<typeof setTimeout> | null = null;

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
    config.value = await api.get<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`);
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
    config.value = await api.put<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`, {
      channel_id: config.value.channel_id,
      message: config.value.message,
      enabled: config.value.enabled,
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
      <h2 class="text-lg font-semibold">Leave Messages</h2>
      <p class="text-muted-foreground text-sm">
        Post a custom message to a channel whenever a member leaves or is removed from the server. Use
        <code class="font-mono text-xs">{user}</code> in the message text to mention the departing member by name.
        Changes auto-save as you type.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium flex items-center gap-1.5">
          Enabled
          <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="When enabled, the bot will post a leave message each time a member leaves or is removed from the server." />
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5">
          Channel
          <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The text channel where leave messages will be posted. The bot must have permission to send messages in this channel." />
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
          <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The message text to post when a member leaves. Use {user} as a placeholder — it will be replaced with the departing member's username." />
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
      <p v-if="saving" class="text-xs text-muted-foreground">Saving…</p>
      <p v-else-if="success" class="text-xs text-green-400">✓ Saved</p>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
