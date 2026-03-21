<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed, onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { ReminderCreate, ReminderSchema, ReminderUpdate } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();

const { t, locale } = useI18n();

const nextFireFormatter = computed(
  () => new Intl.DateTimeFormat(locale.current, { dateStyle: "medium", timeStyle: "short" }),
);

function formatNextFire(isoStr: string): string {
  try {
    return nextFireFormatter.value.format(new Date(isoStr));
  } catch {
    return isoStr.slice(0, 16).replace("T", " ");
  }
}

const reminders = ref<ReminderSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const showCreate = ref(false);
const saving = ref(false);
const opError = ref<string | null>(null);

const DOW_LABELS = computed(() => [
  t("tabs.reminders.days.monday"),
  t("tabs.reminders.days.tuesday"),
  t("tabs.reminders.days.wednesday"),
  t("tabs.reminders.days.thursday"),
  t("tabs.reminders.days.friday"),
  t("tabs.reminders.days.saturday"),
  t("tabs.reminders.days.sunday"),
]);

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
  return q ? ALL_TIMEZONES.filter((tz) => tz.toLowerCase().includes(q)).slice(0, 80) : ALL_TIMEZONES.slice(0, 80);
});

function selectTz(tz: string) {
  tzQuery.value = tz;
  tzOpen.value = false;
}

function closeTzDropdown() {
  setTimeout(() => {
    tzOpen.value = false;
  }, 150);
}

// ── Draft ──
function blankDraft() {
  return {
    channel_id: "",
    channel_name: "",
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
    error.value = e instanceof Error ? e.message : t("common.load_failed");
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
  if (r.schedule_type === "interval")
    return t("tabs.reminders.schedule.interval", { interval: formatInterval(r.interval_seconds) });
  if (r.schedule_type === "daily") return t("tabs.reminders.schedule.daily", { time: r.schedule_time ?? "?" });
  if (r.schedule_type === "weekly") {
    const dow = r.schedule_day_of_week != null ? (DOW_LABELS.value[r.schedule_day_of_week] ?? "?") : "?";
    return t("tabs.reminders.schedule.weekly", { dow, time: r.schedule_time ?? "?" });
  }
  if (r.schedule_type === "monthly")
    return t("tabs.reminders.schedule.monthly", { dom: r.schedule_day_of_month ?? "?", time: r.schedule_time ?? "?" });
  return r.schedule_type;
}

async function toggleReminder(r: ReminderSchema) {
  try {
    const updated = await api.patch<ReminderSchema>(`/guilds/${props.guildId}/reminders/${r.id}`, {
      enabled: !r.enabled,
    } satisfies ReminderUpdate);
    const idx = reminders.value.findIndex((x) => x.id === r.id);
    if (idx !== -1) reminders.value[idx] = updated;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  }
}

async function deleteReminder(id: number) {
  try {
    await api.delete(`/guilds/${props.guildId}/reminders/${id}`);
    reminders.value = reminders.value.filter((r) => r.id !== id);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}

async function createReminder() {
  saving.value = true;
  opError.value = null;
  try {
    const payload: ReminderCreate = {
      channel_id: draft.value.channel_id,
      channel_name: draft.value.channel_name || null,
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
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">{{ t("tabs.reminders.title") }}</h2>
        <p class="text-muted-foreground text-sm">{{ t("tabs.reminders.desc") }}</p>
      </div>
      <button
        class="flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0"
        @click="showCreate = !showCreate"
      >
        <Icon icon="mdi:plus" class="w-4 h-4" />
        {{ t("tabs.reminders.new") }}
      </button>
    </div>

    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>

    <!-- Create Panel -->
    <div v-if="showCreate" class="bg-card border border-primary rounded p-4 space-y-4">
      <p class="text-sm font-semibold">{{ t("tabs.reminders.new_panel") }}</p>

      <!-- Inline controls: wrap onto next line on small screens -->
      <div class="flex flex-wrap gap-3 items-end">
        <!-- Channel -->
        <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.reminders.channel_label") }}
            <InfoTooltip :text="t('tabs.reminders.channel_tooltip')" />
          </label>
          <DiscordPicker v-model="draft.channel_id" v-model:model-name="draft.channel_name" :guild-id="guildId" kind="channel" />
        </div>

        <!-- Schedule type -->
        <div class="flex flex-col gap-1 flex-1 min-w-[160px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.reminders.schedule_type_label") }}
            <InfoTooltip :text="t('tabs.reminders.schedule_type_tooltip')" />
          </label>
          <select v-model="draft.schedule_type" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option value="interval">{{ t("tabs.reminders.type.interval") }}</option>
            <option value="daily">{{ t("tabs.reminders.type.daily") }}</option>
            <option value="weekly">{{ t("tabs.reminders.type.weekly") }}</option>
            <option value="monthly">{{ t("tabs.reminders.type.monthly") }}</option>
          </select>
        </div>

        <!-- Interval: amount + unit (grouped as one flex item) -->
        <div v-show="draft.schedule_type === 'interval'" class="flex flex-col gap-1 flex-1 min-w-[180px]">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.reminders.repeat_label") }}
            <InfoTooltip :text="t('tabs.reminders.repeat_tooltip')" />
          </label>
          <div class="flex gap-2">
            <input
              v-model.number="intervalAmount"
              type="number"
              :min="UNIT_MIN[intervalUnit]"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-20 shrink-0"
            />
            <select v-model="intervalUnit" class="bg-input border border-border rounded px-3 py-2 text-sm flex-1">
              <option value="minutes">{{ t("tabs.reminders.unit.minutes") }}</option>
              <option value="hours">{{ t("tabs.reminders.unit.hours") }}</option>
              <option value="days">{{ t("tabs.reminders.unit.days") }}</option>
            </select>
          </div>
        </div>

        <!-- Time (daily / weekly / monthly) -->
        <div v-show="draft.schedule_type !== 'interval'" class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.reminders.time_label") }}
            <InfoTooltip :text="t('tabs.reminders.time_tooltip')" />
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
            {{ t("tabs.reminders.dow_label") }}
            <InfoTooltip :text="t('tabs.reminders.dow_tooltip')" />
          </label>
          <select v-model.number="draft.schedule_day_of_week" class="bg-input border border-border rounded px-3 py-2 text-sm">
            <option v-for="(label, i) in DOW_LABELS" :key="i" :value="i">{{ label }}</option>
          </select>
        </div>

        <!-- Day of month (monthly) -->
        <div v-show="draft.schedule_type === 'monthly'" class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.reminders.dom_label") }}
            <InfoTooltip :text="t('tabs.reminders.dom_tooltip')" />
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
            {{ t("tabs.reminders.tz_label") }}
            <InfoTooltip :text="t('tabs.reminders.tz_tooltip')" />
          </label>
          <input
            v-model="tzQuery"
            type="text"
            :placeholder="t('tabs.reminders.tz_placeholder')"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
            @focus="tzOpen = true"
            @blur="closeTzDropdown"
          />
          <div
            v-if="tzOpen"
            class="absolute top-full left-0 right-0 z-20 mt-1 bg-card border border-border rounded shadow-lg max-h-48 overflow-y-auto scrollbar-thin"
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
          {{ t("tabs.reminders.message_label") }}
          <InfoTooltip :text="t('tabs.reminders.message_tooltip')" />
        </label>
        <textarea
          v-model="draft.message"
          rows="3"
          :placeholder="t('tabs.reminders.message_placeholder')"
          class="bg-input border border-border rounded px-3 py-2 text-sm resize-y"
        />
      </div>

      <div class="flex gap-2">
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="saving || !draft.channel_id || !draft.message.trim()"
          @click="createReminder"
        >{{ saving ? t("tabs.reminders.saving") : t("common.create") }}</button>
        <button
          class="text-muted-foreground hover:text-foreground text-sm transition-colors"
          @click="showCreate = false; draft = blankDraft(); intervalAmount = 1; intervalUnit = 'hours'; tzQuery = 'UTC'"
        >{{ t("common.cancel") }}</button>
      </div>
    </div>

    <!-- List -->
    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="reminders.length === 0 && !showCreate" class="text-muted-foreground text-sm">{{ t("tabs.reminders.empty") }}</p>

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
          :title="r.enabled ? t('tabs.reminders.disable') : t('tabs.reminders.enable')"
          @click="toggleReminder(r)"
        >
          <Icon :icon="r.enabled ? 'mdi:bell' : 'mdi:bell-off-outline'" class="w-4 h-4" />
        </button>

        <div class="flex-1 min-w-0 space-y-0.5">
          <div class="font-medium text-sm truncate">{{ r.message ?? t("tabs.reminders.no_message") }}</div>
          <div class="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-0.5">
            <span>{{ r.channel_name ?? r.channel_id }}</span>
            <span>{{ scheduleLabel(r) }}</span>
            <span v-if="r.timezone">{{ r.timezone }}</span>
            <span>{{ t("tabs.reminders.next_fire", { datetime: formatNextFire(r.next_fire) }) }}</span>
            <span>{{ t("tabs.reminders.fired_count", { count: r.count }) }}</span>
          </div>
        </div>

        <!-- Delete -->
        <button
          class="flex-shrink-0 text-muted-foreground hover:text-destructive transition-colors"
          :title="t('common.delete')"
          @click="deleteReminder(r.id)"
        >
          <Icon icon="mdi:delete-outline" class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
