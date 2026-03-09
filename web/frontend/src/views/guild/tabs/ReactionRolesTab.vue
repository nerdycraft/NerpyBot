<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { ReactionRoleMessageSchema } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const messages = ref<ReactionRoleMessageSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    messages.value = await api.get<ReactionRoleMessageSchema[]>(`/guilds/${props.guildId}/reaction-roles`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Reaction Roles</h2>
      <p class="text-muted-foreground text-sm">Messages with reaction-based role assignments (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="messages.length === 0" class="text-muted-foreground text-sm">
      No reaction role messages configured.
    </p>

    <div v-else class="space-y-3">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="bg-card border border-border rounded px-4 py-3 space-y-2"
      >
        <div class="text-sm text-muted-foreground font-mono">
          Channel {{ msg.channel_id }} · Message {{ msg.message_id }}
        </div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="entry in msg.entries"
            :key="entry.role_id"
            class="bg-muted rounded px-2 py-1 text-xs"
          >
            {{ entry.emoji }} → {{ entry.role_id }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
