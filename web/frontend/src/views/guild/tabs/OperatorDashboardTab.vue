<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { onMounted, onUnmounted, ref } from "vue";
import { api } from "@/api/client";
import type { HealthResponse } from "@/api/types";
import { useI18n } from "@/i18n";

const { t } = useI18n();

const health = ref<HealthResponse | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const autoRefresh = ref(false);
let intervalId: ReturnType<typeof setInterval> | null = null;

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts = [d && `${d}d`, h && `${h}h`, m && `${m}m`, s && `${s}s`].filter(Boolean);
  return parts.length ? parts.join(" ") : "0s";
}

async function fetchHealth() {
  if (loading.value) return;
  loading.value = true;
  error.value = null;
  try {
    health.value = await api.get<HealthResponse>("/operator/health");
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("tabs.operator_dashboard.fetch_failed");
    health.value = null;
  } finally {
    loading.value = false;
  }
}

function toggleAutoRefresh() {
  if (autoRefresh.value) {
    intervalId = setInterval(fetchHealth, 30_000);
  } else {
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }
}

onMounted(async () => {
  await fetchHealth();
});

onUnmounted(() => {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
});
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-1">
      <div class="flex items-center gap-2">
        <Icon icon="mdi:heart-pulse" class="w-5 h-5 text-rose-400" />
        <h2 class="text-xl font-bold">{{ t("tabs.operator_dashboard.title") }}</h2>
      </div>
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
          <input
            v-model="autoRefresh"
            type="checkbox"
            class="rounded"
            @change="toggleAutoRefresh"
          />
          {{ t("tabs.operator_dashboard.auto_refresh") }}
        </label>
        <button
          class="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
          :disabled="loading"
          @click="fetchHealth"
        >
          <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          {{ t("common.refresh") }}
        </button>
      </div>
    </div>
    <p class="text-muted-foreground text-sm mb-6">{{ t("tabs.operator_dashboard.desc") }}</p>

    <!-- Loading state -->
    <div v-if="loading && !health" class="flex items-center gap-2 text-muted-foreground text-sm py-4">
      <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
      {{ t("tabs.operator_dashboard.loading") }}
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="text-destructive text-sm py-2">
      {{ error }}
    </div>

    <!-- Unreachable state -->
    <div
      v-else-if="health && health.status === 'unreachable'"
      class="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded px-4 py-3 text-destructive text-sm mb-6"
    >
      <Icon icon="mdi:alert-circle-outline" class="w-5 h-5 flex-shrink-0" />
      {{ t("tabs.operator_dashboard.unreachable") }}
    </div>

    <!-- Metrics -->
    <div v-if="health">
      <!-- Status row -->
      <div class="flex items-center gap-3 mb-6">
        <span class="text-sm text-muted-foreground">{{ t("tabs.operator_dashboard.status") }}</span>
        <span
          :class="[
            'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold',
            health.status === 'online'
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
              : 'bg-destructive/15 text-destructive border border-destructive/30',
          ]"
        >
          <Icon
            :icon="health.status === 'online' ? 'mdi:check-circle-outline' : 'mdi:alert-circle-outline'"
            class="w-3.5 h-3.5"
          />
          {{ health.status === "online" ? t("tabs.operator_dashboard.online") : t("tabs.operator_dashboard.status_unreachable") }}
        </span>
      </div>

      <!-- Metrics grid -->
      <div class="grid grid-cols-2 gap-4 mb-6">
        <!-- Uptime -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:timer-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.uptime") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.uptime_seconds !== null ? formatUptime(health.uptime_seconds) : "—" }}
          </p>
        </div>

        <!-- Latency -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:lightning-bolt-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.latency") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.latency_ms !== null ? `${health.latency_ms} ms` : "—" }}
          </p>
        </div>

        <!-- Guild count -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:server-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.guilds") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.guild_count !== null ? health.guild_count : "—" }}
          </p>
        </div>

        <!-- Active reminders -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:bell-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.active_reminders") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.active_reminders !== null ? health.active_reminders : "—" }}
          </p>
        </div>

        <!-- 24h error count -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:alert-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.errors_24h") }}
          </p>
          <p
            :class="[
              'text-sm font-medium',
              health.error_count_24h !== null && health.error_count_24h > 0 ? 'text-destructive' : '',
            ]"
          >
            {{ health.error_count_24h !== null ? health.error_count_24h : "—" }}
          </p>
        </div>

        <!-- Memory -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:memory" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.memory") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.memory_mb !== null ? `${health.memory_mb} MB` : "—" }}
          </p>
        </div>

        <!-- CPU -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:cpu-64-bit" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.cpu") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.cpu_percent !== null ? `${health.cpu_percent}%` : "—" }}
          </p>
        </div>

        <!-- Voice connections count -->
        <div class="bg-card border border-border rounded px-4 py-3">
          <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
            <Icon icon="mdi:microphone-outline" class="w-3.5 h-3.5" />
            {{ t("tabs.operator_dashboard.voice_connections") }}
          </p>
          <p class="text-sm font-medium">
            {{ health.voice_connections !== null ? health.voice_connections : "—" }}
          </p>
        </div>
      </div>

      <!-- Version info -->
      <div class="bg-card border border-border rounded px-4 py-3 mb-6 space-y-1.5">
        <p class="text-xs text-muted-foreground font-semibold uppercase tracking-wide mb-2">{{ t("tabs.operator_dashboard.version_info") }}</p>
        <div class="flex items-center gap-2 text-sm">
          <span class="text-muted-foreground w-32 flex-shrink-0">{{ t("tabs.operator_dashboard.bot_version") }}</span>
          <span class="font-mono text-xs">{{ health.bot_version ?? "—" }}</span>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <span class="text-muted-foreground w-32 flex-shrink-0">{{ t("tabs.operator_dashboard.python") }}</span>
          <span class="font-mono text-xs">{{ health.python_version ?? "—" }}</span>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <span class="text-muted-foreground w-32 flex-shrink-0">{{ t("tabs.operator_dashboard.discord_py") }}</span>
          <span class="font-mono text-xs">{{ health.discord_py_version ?? "—" }}</span>
        </div>
      </div>

      <!-- Voice connections table -->
      <div v-if="health.voice_details.length > 0">
        <h3 class="text-sm font-semibold mb-2 flex items-center gap-1.5">
          <Icon icon="mdi:microphone-outline" class="w-4 h-4 text-muted-foreground" />
          {{ t("tabs.operator_dashboard.active_voice_sessions") }}
        </h3>
        <div class="border border-border rounded overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-muted/50 border-b border-border">
                <th class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">{{ t("tabs.operator_dashboard.col_guild") }}</th>
                <th class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">{{ t("tabs.operator_dashboard.col_channel") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="vc in health.voice_details"
                :key="vc.channel_id"
                class="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
              >
                <td class="px-4 py-2 text-sm">{{ vc.guild_name }}</td>
                <td class="px-4 py-2 text-sm text-muted-foreground">{{ vc.channel_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
