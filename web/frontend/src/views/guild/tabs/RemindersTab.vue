<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ReminderSchema, ReminderCreate, ReminderUpdate } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";

const props = defineProps<{ guildId: string }>();

const reminders = ref<ReminderSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const showCreate = ref(false);
const saving = ref(false);
const opError = ref<string | null>(null);

const DOW_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function blankDraft(): ReminderCreate {
  return {
    channel_id: "",
    message: "",
    schedule_type: "interval",
    interval_seconds: 3600,
    schedule_time: "09:00",
    schedule_day_of_week: 0,
    schedule_day_of_month: 1,
    timezone: "UTC",
  };
}

const draft = ref<ReminderCreate>(blankDraft());

onMounted(async () => {
  try {
    reminders.value = await api.get<ReminderSchema[]>(`/guilds/${props.guildId}/reminders`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
});

function formatInterval(seconds: number | null): string {
  if (!seconds) return "—";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function scheduleLabel(r: ReminderSchema): string {
  if (r.schedule_type === "interval") return `Every ${formatInterval(r.interval_seconds)}`;
  if (r.schedule_type === "daily") return `Daily at ${r.schedule_time ?? "?"}`;
  if (r.schedule_type === "weekly") {
    const dow = r.schedule_day_of_week != null ? DOW_LABELS[r.schedule_day_of_week] : "?";
    return `Weekly on ${dow} at ${r.schedule_time ?? "?"}`;
  }
  if (r.schedule_type === "monthly") return `Monthly on day ${r.schedule_day_of_month} at ${r.schedule_time ?? "?"}`;
  return r.schedule_type;
}

async function toggleReminder(r: ReminderSchema) {
  try {
    const updated = await api.patch<ReminderSchema>(
      `/guilds/${props.guildId}/reminders/${r.id}`,
      { enabled: !r.enabled } satisfies ReminderUpdate,
    );
    const idx = reminders.value.findIndex((x) => x.id === r.id);
    if (idx !== -1) reminders.value[idx] = updated;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Toggle failed";
  }
}

async function deleteReminder(id: number) {
  try {
    await api.delete(`/guilds/${props.guildId}/reminders/${id}`);
    reminders.value = reminders.value.filter((r) => r.id !== id);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Delete failed";
  }
}

async function createReminder() {
  saving.value = true;
  opError.value = null;
  try {
    const payload: ReminderCreate = {
      channel_id: draft.value.channel_id,
      message: draft.value.message,
      schedule_type: draft.value.schedule_type,
      timezone: draft.value.timezone || "UTC",
    };
    if (draft.value.schedule_type === "interval") {
      payload.interval_seconds = draft.value.interval_seconds;
    } else {
      payload.schedule_time = draft.value.schedule_time;
      if (draft.value.schedule_type === "weekly") payload.schedule_day_of_week = draft.value.schedule_day_of_week;
      if (draft.value.schedule_type === "monthly") payload.schedule_day_of_month = draft.value.schedule_day_of_month;
    }
    const created = await api.post<ReminderSchema>(`/guilds/${props.guildId}/reminders`, payload);
    reminders.value.unshift(created);
    showCreate.value = false;
    draft.value = blankDraft();
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Create failed";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold">Reminders</h2>
        <p class="text-muted-foreground text-sm">Scheduled channel messages. Per-user reminders are Discord-only.</p>
      </div>
      <button
        class="flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors"
        @click="showCreate = !showCreate"
      >
        <Icon icon="mdi:plus" class="w-4 h-4" />
        New Reminder
      </button>
    </div>

    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>

    <!-- Create Panel -->
    <div v-if="showCreate" class="bg-card border border-primary rounded p-4 space-y-4">
      <p class="text-sm font-semibold">New Reminder</p>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Channel</label>
          <DiscordPicker v-model="draft.channel_id" :guild-id="guildId" kind="channel" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Schedule Type</label>
          <select v-model="draft.schedule_type" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option value="interval">Interval (repeat every N seconds)</option>
            <option value="daily">Daily (at a fixed time)</option>
            <option value="weekly">Weekly (day + time)</option>
            <option value="monthly">Monthly (day-of-month + time)</option>
          </select>
        </div>

        <!-- Interval: seconds input -->
        <div v-show="draft.schedule_type === 'interval'" class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Interval (seconds)</label>
          <input
            v-model.number="draft.interval_seconds"
            type="number"
            min="60"
            step="60"
            placeholder="3600"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          />
          <span class="text-xs text-muted-foreground">
            {{ draft.interval_seconds ? formatInterval(draft.interval_seconds) : "" }}
          </span>
        </div>

        <!-- Time (daily / weekly / monthly) -->
        <div v-show="draft.schedule_type !== 'interval'" class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Time (HH:MM)</label>
          <input
            v-model="draft.schedule_time"
            type="time"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          />
        </div>

        <!-- Day of week (weekly) -->
        <div v-show="draft.schedule_type === 'weekly'" class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Day of Week</label>
          <select v-model.number="draft.schedule_day_of_week" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option v-for="(label, i) in DOW_LABELS" :key="i" :value="i">{{ label }}</option>
          </select>
        </div>

        <!-- Day of month (monthly) -->
        <div v-show="draft.schedule_type === 'monthly'" class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Day of Month (1–28)</label>
          <input
            v-model.number="draft.schedule_day_of_month"
            type="number"
            min="1"
            max="28"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-24"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Timezone</label>
          <input
            v-model="draft.timezone"
            type="text"
            placeholder="UTC"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          />
        </div>

        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-xs text-muted-foreground">Message</label>
          <textarea
            v-model="draft.message"
            rows="3"
            placeholder="Message to post in the channel…"
            class="bg-input border border-border rounded px-3 py-2 text-sm resize-y"
          />
        </div>
      </div>

      <div class="flex gap-2">
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="saving || !draft.channel_id || !draft.message.trim()"
          @click="createReminder"
        >{{ saving ? "Saving…" : "Create" }}</button>
        <button
          class="text-muted-foreground hover:text-foreground text-sm transition-colors"
          @click="showCreate = false; draft = blankDraft()"
        >Cancel</button>
      </div>
    </div>

    <!-- List -->
    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="reminders.length === 0 && !showCreate" class="text-muted-foreground text-sm">No reminders configured.</p>

    <div v-else class="space-y-2">
      <div
        v-for="r in reminders"
        :key="r.id"
        class="bg-card border border-border rounded px-4 py-3 flex items-start gap-3"
      >
        <!-- Toggle -->
        <button
          :class="r.enabled ? 'text-green-400 hover:text-green-300' : 'text-muted-foreground hover:text-foreground'"
          class="flex-shrink-0 mt-0.5 transition-colors"
          :title="r.enabled ? 'Disable' : 'Enable'"
          @click="toggleReminder(r)"
        >
          <Icon :icon="r.enabled ? 'mdi:bell' : 'mdi:bell-off-outline'" class="w-4 h-4" />
        </button>

        <div class="flex-1 min-w-0 space-y-0.5">
          <div class="font-medium text-sm truncate">{{ r.message ?? "(no message)" }}</div>
          <div class="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-0.5">
            <span>{{ r.channel_name ?? r.channel_id }}</span>
            <span>{{ scheduleLabel(r) }}</span>
            <span v-if="r.timezone">{{ r.timezone }}</span>
            <span>Next: {{ r.next_fire.slice(0, 16).replace("T", " ") }}</span>
            <span>Fired {{ r.count }}×</span>
          </div>
        </div>

        <!-- Delete -->
        <button
          class="flex-shrink-0 text-muted-foreground hover:text-destructive transition-colors"
          title="Delete"
          @click="deleteReminder(r.id)"
        >
          <Icon icon="mdi:delete-outline" class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
