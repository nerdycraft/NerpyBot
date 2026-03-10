<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
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

// ── Interval picker state (separate from the draft's interval_seconds) ──
type IntervalUnit = "minutes" | "hours" | "days";
const intervalAmount = ref(1);
const intervalUnit = ref<IntervalUnit>("hours");

const UNIT_SECONDS: Record<IntervalUnit, number> = { minutes: 60, hours: 3600, days: 86400 };
const UNIT_MIN: Record<IntervalUnit, number> = { minutes: 1, hours: 1, days: 1 };

// ── Timezone autocomplete ──
const ALL_TIMEZONES: string[] = Intl.supportedValuesOf("timeZone");
const tzQuery = ref("UTC");
const tzOpen = ref(false);
const filteredTz = computed(() => {
  const q = tzQuery.value.toLowerCase();
  return q
    ? ALL_TIMEZONES.filter((tz) => tz.toLowerCase().includes(q)).slice(0, 80)
    : ALL_TIMEZONES.slice(0, 80);
});

function selectTz(tz: string) {
  tzQuery.value = tz;
  tzOpen.value = false;
}

function closeTzDropdown() {
  setTimeout(() => { tzOpen.value = false; }, 150);
}

// ── Draft ──
function blankDraft() {
  return {
    channel_id: "",
    message: "",
    schedule_type: "interval" as ReminderCreate["schedule_type"],
    schedule_time: "09:00",
    schedule_day_of_week: 0,
    schedule_day_of_month: 1,
  };
}

const draft = ref(blankDraft());

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
  if (seconds % 86400 === 0) return `${seconds / 86400}d`;
  if (seconds % 3600 === 0) return `${seconds / 3600}h`;
  if (seconds % 60 === 0) return `${seconds / 60}m`;
  return `${seconds}s`;
}

function scheduleLabel(r: ReminderSchema): string {
  if (r.schedule_type === "interval") return `Every ${formatInterval(r.interval_seconds)}`;
  if (r.schedule_type === "daily") return `Daily at ${r.schedule_time ?? "?"}`;
  if (r.schedule_type === "weekly") {
    const dow = r.schedule_day_of_week != null ? DOW_LABELS[r.schedule_day_of_week] : "?";
    return `Weekly · ${dow} at ${r.schedule_time ?? "?"}`;
  }
  if (r.schedule_type === "monthly") return `Monthly · day ${r.schedule_day_of_month} at ${r.schedule_time ?? "?"}`;
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
      timezone: tzQuery.value || "UTC",
    };
    if (draft.value.schedule_type === "interval") {
      payload.interval_seconds = intervalAmount.value * UNIT_SECONDS[intervalUnit.value];
    } else {
      payload.schedule_time = draft.value.schedule_time;
      if (draft.value.schedule_type === "weekly") payload.schedule_day_of_week = draft.value.schedule_day_of_week;
      if (draft.value.schedule_type === "monthly") payload.schedule_day_of_month = draft.value.schedule_day_of_month;
    }
    const created = await api.post<ReminderSchema>(`/guilds/${props.guildId}/reminders`, payload);
    reminders.value.unshift(created);
    showCreate.value = false;
    draft.value = blankDraft();
    intervalAmount.value = 1;
    intervalUnit.value = "hours";
    tzQuery.value = "UTC";
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
        <p class="text-muted-foreground text-sm">
          Reminders post a message to a Discord channel on a recurring schedule — every N minutes/hours/days, daily, weekly, or monthly.
          Each reminder can be individually enabled or disabled; the bot tracks how many times each one has fired and when the next fire is due.
        </p>
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

      <!-- Inline controls: wrap onto next line on small screens -->
      <div class="flex flex-wrap gap-3 items-end">
        <!-- Channel -->
        <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Channel
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The Discord channel where the reminder message will be posted." />
          </label>
          <DiscordPicker v-model="draft.channel_id" :guild-id="guildId" kind="channel" />
        </div>

        <!-- Schedule type -->
        <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Schedule Type
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="How often the reminder fires: a repeating interval, or a fixed time each day, week, or month." />
          </label>
          <select v-model="draft.schedule_type" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option value="interval">Repeat every…</option>
            <option value="daily">Daily at a fixed time</option>
            <option value="weekly">Weekly (day + time)</option>
            <option value="monthly">Monthly (day + time)</option>
          </select>
        </div>

        <!-- Interval: amount + unit (grouped as one flex item) -->
        <div v-show="draft.schedule_type === 'interval'" class="flex flex-col gap-1 flex-1 min-w-[180px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Repeat every
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The interval between fires. Enter a number and choose minutes, hours, or days." />
          </label>
          <div class="flex gap-2">
            <input
              v-model.number="intervalAmount"
              type="number"
              :min="UNIT_MIN[intervalUnit]"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-20 shrink-0"
            />
            <select v-model="intervalUnit" class="bg-input border border-border rounded px-3 py-2 text-sm flex-1">
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
              <option value="days">Days</option>
            </select>
          </div>
        </div>

        <!-- Time (daily / weekly / monthly) -->
        <div v-show="draft.schedule_type !== 'interval'" class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Time
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The time of day the reminder fires, interpreted in the selected timezone." />
          </label>
          <input
            v-model="draft.schedule_time"
            type="time"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          />
        </div>

        <!-- Day of week (weekly) -->
        <div v-show="draft.schedule_type === 'weekly'" class="flex flex-col gap-1 flex-1 min-w-[140px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Day of Week
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="Which day of the week the reminder fires for weekly schedules." />
          </label>
          <select v-model.number="draft.schedule_day_of_week" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option v-for="(label, i) in DOW_LABELS" :key="i" :value="i">{{ label }}</option>
          </select>
        </div>

        <!-- Day of month (monthly) -->
        <div v-show="draft.schedule_type === 'monthly'" class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Day of Month (1–28)
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="Which day of the month the reminder fires. Capped at 28 to ensure it fires every month." />
          </label>
          <input
            v-model.number="draft.schedule_day_of_month"
            type="number"
            min="1"
            max="28"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-24"
          />
        </div>

        <!-- Timezone autocomplete -->
        <div class="flex flex-col gap-1 relative flex-1 min-w-[180px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Timezone
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The timezone used to interpret the schedule time. Defaults to UTC if left blank." />
          </label>
          <input
            v-model="tzQuery"
            type="text"
            placeholder="Search timezone…"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
            @focus="tzOpen = true"
            @blur="closeTzDropdown"
          />
          <div
            v-if="tzOpen"
            class="absolute top-full left-0 right-0 z-20 mt-1 bg-card border border-border rounded shadow-lg max-h-48 overflow-y-auto"
          >
            <button
              v-for="tz in filteredTz"
              :key="tz"
              class="w-full text-left px-3 py-1.5 text-sm hover:bg-muted transition-colors"
              :class="{ 'bg-primary/10 text-primary': tzQuery === tz }"
              @mousedown.prevent="selectTz(tz)"
            >
              {{ tz }}
            </button>
          </div>
        </div>
      </div>

      <!-- Message: always full width -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium flex items-center gap-1.5">
          Message
          <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="The text content that will be posted to the channel each time the reminder fires." />
        </label>
        <textarea
          v-model="draft.message"
          rows="3"
          placeholder="Message to post in the channel…"
          class="bg-input border border-border rounded px-3 py-2 text-sm resize-y"
        />
      </div>

      <div class="flex gap-2">
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="saving || !draft.channel_id || !draft.message.trim()"
          @click="createReminder"
        >{{ saving ? "Saving…" : "Create" }}</button>
        <button
          class="text-muted-foreground hover:text-foreground text-sm transition-colors"
          @click="showCreate = false; draft = blankDraft(); intervalAmount = 1; intervalUnit = 'hours'; tzQuery = 'UTC'"
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
