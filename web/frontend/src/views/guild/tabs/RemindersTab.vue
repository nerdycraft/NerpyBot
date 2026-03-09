<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { ReminderSchema } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const reminders = ref<ReminderSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    reminders.value = await api.get<ReminderSchema[]>(`/guilds/${props.guildId}/reminders`);
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
      <h2 class="text-lg font-semibold">Reminders</h2>
      <p class="text-muted-foreground text-sm">Active scheduled reminders for this server (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="reminders.length === 0" class="text-muted-foreground text-sm">No reminders configured.</p>

    <div v-else class="space-y-3">
      <div
        v-for="r in reminders"
        :key="r.id"
        class="bg-card border border-border rounded px-4 py-3 space-y-1"
      >
        <div class="flex items-start justify-between gap-2">
          <span class="font-medium text-sm">{{ r.message ?? "(no message)" }}</span>
          <span
            :class="r.enabled ? 'text-green-400' : 'text-muted-foreground'"
            class="text-xs flex-shrink-0"
          >
            {{ r.enabled ? "Active" : "Disabled" }}
          </span>
        </div>
        <div class="text-muted-foreground text-xs flex flex-wrap gap-x-4 gap-y-1">
          <span>Channel: {{ r.channel_name ?? r.channel_id }}</span>
          <span>Schedule: {{ r.schedule_type }}</span>
          <span>Next: {{ r.next_fire }}</span>
          <span>Count: {{ r.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
