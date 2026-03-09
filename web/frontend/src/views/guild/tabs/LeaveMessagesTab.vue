<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { LeaveMessageConfig } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const config = ref<LeaveMessageConfig | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref<string | null>(null);
const success = ref(false);

onMounted(async () => {
  try {
    config.value = await api.get<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`);
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
    config.value = await api.put<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`, {
      channel_id: config.value.channel_id,
      message: config.value.message,
      enabled: config.value.enabled,
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
      <h2 class="text-lg font-semibold">Leave Messages</h2>
      <p class="text-muted-foreground text-sm">Post a message when a member leaves the server.</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium">Enabled</span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="leave-channel">Channel ID</label>
        <input
          id="leave-channel"
          v-model="config.channel_id"
          type="text"
          placeholder="Channel ID"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-64"
        />
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="leave-message">Message</label>
        <textarea
          id="leave-message"
          v-model="config.message"
          rows="3"
          placeholder="Goodbye {user}!"
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
