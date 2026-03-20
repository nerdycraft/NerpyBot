<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/api/client";
import type {
  BotPermissionGuildResult,
  BotPermissionSubscription,
  BotPermissionsResponse,
  DebugToggleResponse,
  ErrorActionResponse,
  ErrorStatusResponse,
  HealthResponse,
} from "@/api/types";
import SubTabBar from "@/components/SubTabBar.vue";
import { useHealthStatus } from "@/composables/useHealthStatus";
import { useI18n } from "@/i18n";

const { t } = useI18n();

// ── Sub-tab ──────────────────────────────────────────────────────────────────

type SubTab = "health" | "permissions" | "error_control";
const activeTab = ref<SubTab>("health");

// ── Health tab ────────────────────────────────────────────────────────────────

const health = ref<HealthResponse | null>(null);
const healthLoading = ref(false);
const healthError = ref<string | null>(null);

const { status: liveStatus, connected: liveConnected, error: liveError, connect } = useHealthStatus();

const live = computed(() => ({
  uptime_seconds: liveStatus.value?.uptime_seconds ?? health.value?.uptime_seconds ?? null,
  latency_ms: liveStatus.value?.latency_ms ?? health.value?.latency_ms ?? null,
  memory_mb: liveStatus.value?.memory_mb ?? health.value?.memory_mb ?? null,
  cpu_percent: liveStatus.value?.cpu_percent ?? health.value?.cpu_percent ?? null,
  voice_connections: liveStatus.value?.voice_connections ?? health.value?.voice_connections ?? null,
  voice_details: liveStatus.value?.voice_details ?? health.value?.voice_details ?? [],
}));

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  const parts = [d && `${d}d`, h && `${h}h`, m && `${m}m`, s && `${s}s`].filter(Boolean);
  return parts.length ? parts.join(" ") : "0s";
}

async function fetchHealth() {
  if (healthLoading.value) return;
  healthLoading.value = true;
  healthError.value = null;
  try {
    health.value = await api.get<HealthResponse>("/operator/health");
  } catch (e: unknown) {
    healthError.value = e instanceof Error ? e.message : t("tabs.operator_dashboard.fetch_failed");
    health.value = null;
  } finally {
    healthLoading.value = false;
  }
}

// ── Permissions tab ───────────────────────────────────────────────────────────

const permissions = ref<BotPermissionGuildResult[]>([]);
const subscriptions = ref<Set<string>>(new Set());
const permLoading = ref(false);
const permFetched = ref(false);
const permError = ref<string | null>(null);
const pendingSubGuild = ref<string | null>(null);

async function fetchPermissions() {
  if (permLoading.value) return;
  permLoading.value = true;
  permError.value = null;
  try {
    const [permRes, subRes] = await Promise.all([
      api.get<BotPermissionsResponse>("/operator/bot-permissions"),
      api.get<BotPermissionSubscription[]>("/operator/bot-permissions/subscriptions"),
    ]);
    permissions.value = permRes.guilds;
    subscriptions.value = new Set(subRes.map((s) => s.guild_id));
  } catch (e: unknown) {
    permError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    permLoading.value = false;
    permFetched.value = true;
  }
}

async function toggleSubscription(guildId: string) {
  pendingSubGuild.value = guildId;
  try {
    if (subscriptions.value.has(guildId)) {
      await api.delete(`/operator/bot-permissions/subscriptions/${guildId}`);
      subscriptions.value.delete(guildId);
    } else {
      await api.post<BotPermissionSubscription>(`/operator/bot-permissions/subscriptions/${guildId}`, {});
      subscriptions.value.add(guildId);
    }
    subscriptions.value = new Set(subscriptions.value);
  } catch {
    // ignore — subscription state unchanged
  } finally {
    pendingSubGuild.value = null;
  }
}

// ── Error control tab ─────────────────────────────────────────────────────────

const errorStatus = ref<ErrorStatusResponse | null>(null);
const errorLoading = ref(false);
const errorError = ref<string | null>(null);
const suppressDuration = ref("");
const suppressLoading = ref(false);
const suppressMessage = ref<string | null>(null);
const resumeLoading = ref(false);
const debugLoading = ref(false);
const debugMessage = ref<string | null>(null);

function formatSeconds(seconds: number): string {
  const total = Math.round(seconds);
  if (total >= 86400) {
    const d = Math.floor(total / 86400);
    const h = Math.floor((total % 86400) / 3600);
    return h ? `${d}d ${h}h` : `${d}d`;
  }
  if (total >= 3600) {
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    return m ? `${h}h ${m}m` : `${h}h`;
  }
  const m = Math.floor(total / 60);
  return m ? `${m}m` : `${total}s`;
}

async function fetchErrorStatus() {
  if (errorLoading.value) return;
  errorLoading.value = true;
  errorError.value = null;
  try {
    errorStatus.value = await api.get<ErrorStatusResponse>("/operator/error-status");
  } catch (e: unknown) {
    errorError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    errorLoading.value = false;
  }
}

async function suppressErrors() {
  if (!suppressDuration.value.trim()) return;
  suppressLoading.value = true;
  suppressMessage.value = null;
  try {
    const res = await api.post<ErrorActionResponse>("/operator/error-suppress", {
      duration: suppressDuration.value.trim(),
    });
    if (res.success) {
      suppressDuration.value = "";
      await fetchErrorStatus();
    } else {
      suppressMessage.value = res.error ?? t("common.save_failed");
    }
  } catch (e: unknown) {
    suppressMessage.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    suppressLoading.value = false;
  }
}

async function resumeErrors() {
  resumeLoading.value = true;
  try {
    await api.post<ErrorActionResponse>("/operator/error-resume", {});
    await fetchErrorStatus();
  } catch {
    // ignore
  } finally {
    resumeLoading.value = false;
  }
}

async function toggleDebug() {
  debugLoading.value = true;
  debugMessage.value = null;
  try {
    const res = await api.post<DebugToggleResponse>("/operator/debug-toggle", {});
    if (errorStatus.value) errorStatus.value.debug_enabled = res.debug_enabled;
  } catch (e: unknown) {
    debugMessage.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    debugLoading.value = false;
  }
}

// ── Tab lazy-load watcher ──────────────────────────────────────────────────────

watch(activeTab, (tab) => {
  if (tab === "permissions" && !permFetched.value && !permLoading.value) fetchPermissions();
  if (tab === "error_control" && !errorStatus.value && !errorLoading.value) fetchErrorStatus();
});

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  fetchHealth();
  connect();
});
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center gap-2 mb-1">
      <Icon icon="mdi:heart-pulse" class="w-5 h-5 text-rose-400" />
      <h2 class="text-xl font-bold">{{ t("tabs.operator_dashboard.title") }}</h2>
    </div>
    <p class="text-muted-foreground text-sm mb-4">{{ t("tabs.operator_dashboard.desc") }}</p>

    <!-- Sub-tab bar -->
    <SubTabBar>
      <button :class="['subtab-btn', { active: activeTab === 'health' }]" @click="activeTab = 'health'">
        <Icon icon="mdi:heart-pulse" />
        {{ t("tabs.operator_dashboard.tab_health") }}
      </button>
      <button
        :class="['subtab-btn', { active: activeTab === 'permissions' }]"
        @click="activeTab = 'permissions'"
      >
        <Icon icon="mdi:shield-check-outline" />
        {{ t("tabs.operator_dashboard.tab_permissions") }}
      </button>
      <button
        :class="['subtab-btn', { active: activeTab === 'error_control' }]"
        @click="activeTab = 'error_control'"
      >
        <Icon icon="mdi:bell-cog-outline" />
        {{ t("tabs.operator_dashboard.tab_error_control") }}
      </button>
    </SubTabBar>

    <!-- ── Health tab ── -->
    <template v-if="activeTab === 'health'">
      <div class="flex items-center justify-between mb-4">
        <span class="flex items-center gap-2 flex-wrap">
          <span class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              :class="['w-2 h-2 rounded-full', liveConnected ? 'bg-emerald-400 animate-pulse' : 'bg-muted-foreground/40']"
            />
            {{ liveConnected ? t("tabs.operator_dashboard.live") : t("tabs.operator_dashboard.not_live") }}
          </span>
          <span v-if="liveError" class="text-xs text-destructive">{{ liveError }}</span>
        </span>
        <button
          class="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
          :disabled="healthLoading"
          @click="fetchHealth"
        >
          <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': healthLoading }" />
          {{ t("common.refresh") }}
        </button>
      </div>

      <div v-if="healthLoading && !health" class="flex items-center gap-2 text-muted-foreground text-sm py-4">
        <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
        {{ t("tabs.operator_dashboard.loading") }}
      </div>
      <div v-else-if="healthError" class="text-destructive text-sm py-2">{{ healthError }}</div>
      <div
        v-else-if="health && health.status === 'unreachable'"
        class="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded px-4 py-3 text-destructive text-sm mb-6"
      >
        <Icon icon="mdi:alert-circle-outline" class="w-5 h-5 flex-shrink-0" />
        {{ t("tabs.operator_dashboard.unreachable") }}
      </div>

      <div v-if="health || liveStatus">
        <div v-if="health" class="flex items-center gap-3 mb-6">
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
            {{
              health.status === "online"
                ? t("tabs.operator_dashboard.online")
                : t("tabs.operator_dashboard.status_unreachable")
            }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-4 mb-6">
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:timer-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.uptime") }}
            </p>
            <p class="text-sm font-medium">
              {{ live.uptime_seconds !== null ? formatUptime(live.uptime_seconds) : "—" }}
            </p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:lightning-bolt-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.latency") }}
            </p>
            <p class="text-sm font-medium">
              {{ live.latency_ms !== null ? `${live.latency_ms} ms` : "—" }}
            </p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:server-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.guilds") }}
            </p>
            <p class="text-sm font-medium">{{ health?.guild_count ?? "—" }}</p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:bell-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.active_reminders") }}
            </p>
            <p class="text-sm font-medium">
              {{ health?.active_reminders ?? "—" }}
            </p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:alert-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.errors_24h") }}
            </p>
            <p
              :class="[
                'text-sm font-medium',
                (health?.error_count_24h ?? 0) > 0 ? 'text-destructive' : '',
              ]"
            >
              {{ health?.error_count_24h ?? "—" }}
            </p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:memory" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.memory") }}
            </p>
            <p class="text-sm font-medium">{{ live.memory_mb !== null ? `${live.memory_mb} MB` : "—" }}</p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:cpu-64-bit" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.cpu") }}
            </p>
            <p class="text-sm font-medium">{{ live.cpu_percent !== null ? `${live.cpu_percent}%` : "—" }}</p>
          </div>
          <div class="bg-card border border-border rounded px-4 py-3">
            <p class="text-xs text-muted-foreground mb-1 flex items-center gap-1">
              <Icon icon="mdi:microphone-outline" class="w-3.5 h-3.5" />
              {{ t("tabs.operator_dashboard.voice_connections") }}
            </p>
            <p class="text-sm font-medium">
              {{ live.voice_connections !== null ? live.voice_connections : "—" }}
            </p>
          </div>
        </div>

        <div v-if="health" class="bg-card border border-border rounded px-4 py-3 mb-6 space-y-1.5">
          <p class="text-xs text-muted-foreground font-semibold uppercase tracking-wide mb-2">
            {{ t("tabs.operator_dashboard.version_info") }}
          </p>
          <div class="flex items-center gap-2 text-sm">
            <span class="text-muted-foreground w-32 flex-shrink-0">{{
              t("tabs.operator_dashboard.bot_version")
            }}</span>
            <span class="font-mono text-xs">{{ health.bot_version ?? "—" }}</span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="text-muted-foreground w-32 flex-shrink-0">{{ t("tabs.operator_dashboard.python") }}</span>
            <span class="font-mono text-xs">{{ health.python_version ?? "—" }}</span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="text-muted-foreground w-32 flex-shrink-0">{{
              t("tabs.operator_dashboard.discord_py")
            }}</span>
            <span class="font-mono text-xs">{{ health.discord_py_version ?? "—" }}</span>
          </div>
        </div>

        <div v-if="live.voice_details.length > 0">
          <h3 class="text-sm font-semibold mb-2 flex items-center gap-1.5">
            <Icon icon="mdi:microphone-outline" class="w-4 h-4 text-muted-foreground" />
            {{ t("tabs.operator_dashboard.active_voice_sessions") }}
          </h3>
          <div class="border border-border rounded overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-muted/50 border-b border-border">
                  <th
                    class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide"
                  >
                    {{ t("tabs.operator_dashboard.col_guild") }}
                  </th>
                  <th
                    class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide"
                  >
                    {{ t("tabs.operator_dashboard.col_channel") }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="vc in live.voice_details"
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
    </template>

    <!-- ── Bot Permissions tab ── -->
    <template v-else-if="activeTab === 'permissions'">
      <div class="flex items-start justify-between gap-4 mb-4">
        <p class="text-sm text-muted-foreground">{{ t("tabs.operator_dashboard.permissions_desc") }}</p>
        <button
          class="flex-shrink-0 px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
          :disabled="permLoading"
          @click="fetchPermissions"
        >
          <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': permLoading }" />
          {{ t("common.refresh") }}
        </button>
      </div>

      <div v-if="permLoading && !permissions.length" class="flex items-center gap-2 text-muted-foreground text-sm py-4">
        <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
        {{ t("tabs.operator_dashboard.permissions_loading") }}
      </div>
      <div v-else-if="permError" class="text-destructive text-sm py-2">{{ permError }}</div>
      <div v-else-if="!permissions.length" class="text-muted-foreground text-sm py-4">
        {{ t("tabs.operator_dashboard.permissions_empty") }}
      </div>

      <div v-else class="border border-border rounded overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-muted/50 border-b border-border">
              <th class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {{ t("tabs.operator_dashboard.permissions_col_guild") }}
              </th>
              <th class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {{ t("tabs.operator_dashboard.permissions_col_status") }}
              </th>
              <th class="text-left px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {{ t("tabs.operator_dashboard.permissions_col_missing") }}
              </th>
              <th class="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="guild in permissions"
              :key="guild.guild_id"
              class="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
            >
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2">
                  <img
                    v-if="guild.guild_icon"
                    :src="`https://cdn.discordapp.com/icons/${guild.guild_id}/${guild.guild_icon}.webp?size=32`"
                    class="w-6 h-6 rounded-full"
                    :alt="guild.guild_name"
                  />
                  <Icon v-else icon="mdi:server-outline" class="w-6 h-6 text-muted-foreground/50" />
                  <span class="font-medium">{{ guild.guild_name }}</span>
                </div>
              </td>
              <td class="px-4 py-2.5">
                <span
                  :class="[
                    'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold',
                    guild.all_ok
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                      : 'bg-destructive/15 text-destructive border border-destructive/30',
                  ]"
                >
                  <Icon
                    :icon="guild.all_ok ? 'mdi:check-circle-outline' : 'mdi:alert-circle-outline'"
                    class="w-3.5 h-3.5"
                  />
                  {{
                    guild.all_ok
                      ? t("tabs.operator_dashboard.permissions_all_ok")
                      : t("tabs.operator_dashboard.permissions_missing", { count: guild.missing.length })
                  }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span v-if="guild.all_ok" class="text-muted-foreground/50 text-xs">—</span>
                <div v-else class="flex flex-wrap gap-1">
                  <span
                    v-for="perm in guild.missing"
                    :key="perm"
                    class="inline-block px-1.5 py-0.5 rounded text-xs font-mono bg-destructive/10 text-destructive border border-destructive/20"
                  >
                    {{ perm }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  :class="[
                    'px-2.5 py-1 rounded text-xs font-medium border transition-colors disabled:opacity-40',
                    subscriptions.has(guild.guild_id)
                      ? 'bg-primary/10 text-primary border-primary/30 hover:bg-primary/20'
                      : 'bg-muted/50 text-muted-foreground border-border hover:bg-muted',
                  ]"
                  :disabled="pendingSubGuild === guild.guild_id"
                  :title="
                    subscriptions.has(guild.guild_id)
                      ? t('tabs.operator_dashboard.permissions_subscribed_tip')
                      : undefined
                  "
                  @click="toggleSubscription(guild.guild_id)"
                >
                  <Icon
                    v-if="pendingSubGuild === guild.guild_id"
                    icon="mdi:loading"
                    class="w-3 h-3 animate-spin inline mr-1"
                  />
                  {{
                    subscriptions.has(guild.guild_id)
                      ? t("tabs.operator_dashboard.permissions_unsubscribe")
                      : t("tabs.operator_dashboard.permissions_subscribe")
                  }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ── Error Control tab ── -->
    <template v-else-if="activeTab === 'error_control'">
      <div class="flex items-start justify-between gap-4 mb-4">
        <p class="text-sm text-muted-foreground">{{ t("tabs.operator_dashboard.error_control_desc") }}</p>
        <button
          class="flex-shrink-0 px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
          :disabled="errorLoading"
          @click="fetchErrorStatus"
        >
          <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': errorLoading }" />
          {{ t("common.refresh") }}
        </button>
      </div>

      <div v-if="errorError" class="text-destructive text-sm mb-4">{{ errorError }}</div>

      <!-- Notification status card -->
      <div class="bg-card border border-border rounded mb-4 overflow-hidden">
        <div class="bg-muted/50 border-b border-border px-4 py-2.5 flex items-center gap-2">
          <Icon icon="mdi:bell-outline" class="w-4 h-4 text-muted-foreground" />
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {{ t("tabs.operator_dashboard.error_status_title") }}
          </span>
        </div>
        <div class="px-4 py-3">
          <div v-if="errorLoading && !errorStatus" class="flex items-center gap-2 text-muted-foreground text-sm">
            <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
            {{ t("common.loading") }}
          </div>
          <div v-else-if="errorStatus">
            <div class="flex items-center gap-3 mb-3">
              <span
                :class="[
                  'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold',
                  errorStatus.is_suppressed
                    ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                    : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
                ]"
              >
                <Icon
                  :icon="errorStatus.is_suppressed ? 'mdi:bell-off-outline' : 'mdi:bell-check-outline'"
                  class="w-3.5 h-3.5"
                />
                {{
                  errorStatus.is_suppressed
                    ? t("tabs.operator_dashboard.error_suppressed", {
                        remaining: formatSeconds(errorStatus.suppressed_remaining ?? 0),
                      })
                    : t("tabs.operator_dashboard.error_active")
                }}
              </span>
              <button
                v-if="errorStatus.is_suppressed"
                class="px-3 py-1 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors disabled:opacity-40"
                :disabled="resumeLoading"
                @click="resumeErrors"
              >
                <Icon v-if="resumeLoading" icon="mdi:loading" class="w-3 h-3 animate-spin inline mr-1" />
                {{
                  resumeLoading
                    ? t("tabs.operator_dashboard.error_resuming")
                    : t("tabs.operator_dashboard.error_resume_button")
                }}
              </button>
            </div>

            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              {{ t("tabs.operator_dashboard.error_buckets_title") }}
              <span class="text-muted-foreground/50 normal-case font-normal ml-1">
                ({{ errorStatus.throttle_window / 60 }}m window)
              </span>
            </p>
            <p v-if="!Object.keys(errorStatus.buckets).length" class="text-muted-foreground text-sm">
              {{ t("tabs.operator_dashboard.error_buckets_empty") }}
            </p>
            <div v-else class="space-y-1.5">
              <div
                v-for="(bucket, key) in errorStatus.buckets"
                :key="key"
                class="flex items-start justify-between text-sm"
              >
                <span class="font-mono text-xs text-muted-foreground break-all mr-4">{{ key }}</span>
                <div class="flex-shrink-0 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{{
                    t("tabs.operator_dashboard.error_bucket_last", {
                      ago: formatSeconds(bucket.last_notified_ago),
                    })
                  }}</span>
                  <span v-if="bucket.suppressed_count" class="text-amber-400">
                    {{
                      t("tabs.operator_dashboard.error_bucket_suppressed", {
                        count: bucket.suppressed_count,
                      })
                    }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Suppress form -->
      <div class="bg-card border border-border rounded mb-4 overflow-hidden">
        <div class="bg-muted/50 border-b border-border px-4 py-2.5 flex items-center gap-2">
          <Icon icon="mdi:bell-off-outline" class="w-4 h-4 text-muted-foreground" />
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {{ t("tabs.operator_dashboard.error_suppress_title") }}
          </span>
        </div>
        <div class="px-4 py-3">
          <p v-if="suppressMessage" class="text-destructive text-sm mb-3">{{ suppressMessage }}</p>
          <div class="flex gap-2">
            <input
              v-model="suppressDuration"
              type="text"
              :placeholder="t('tabs.operator_dashboard.error_suppress_duration_placeholder')"
              class="flex-1 rounded border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              @keydown.enter="suppressErrors"
            />
            <button
              class="px-4 py-1.5 rounded bg-amber-500/80 text-white text-sm font-medium disabled:opacity-50 hover:bg-amber-500 transition-colors flex items-center gap-1.5"
              :disabled="suppressLoading || !suppressDuration.trim()"
              @click="suppressErrors"
            >
              <Icon v-if="suppressLoading" icon="mdi:loading" class="w-4 h-4 animate-spin" />
              {{
                suppressLoading
                  ? t("tabs.operator_dashboard.error_suppressing")
                  : t("tabs.operator_dashboard.error_suppress_button")
              }}
            </button>
          </div>
        </div>
      </div>

      <!-- Debug toggle -->
      <div class="bg-card border border-border rounded overflow-hidden">
        <div class="bg-muted/50 border-b border-border px-4 py-2.5 flex items-center gap-2">
          <Icon icon="mdi:bug-outline" class="w-4 h-4 text-muted-foreground" />
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {{ t("tabs.operator_dashboard.debug_title") }}
          </span>
        </div>
        <div class="px-4 py-3 flex items-center justify-between">
          <div>
            <p class="text-sm">
              {{
                errorStatus?.debug_enabled != null
                  ? errorStatus.debug_enabled
                    ? t("tabs.operator_dashboard.debug_enabled")
                    : t("tabs.operator_dashboard.debug_disabled")
                  : "—"
              }}
            </p>
            <p v-if="debugMessage" class="text-destructive text-xs mt-1">{{ debugMessage }}</p>
          </div>
          <button
            class="px-3 py-1.5 rounded border border-border bg-muted/50 text-sm font-medium disabled:opacity-50 hover:bg-muted transition-colors flex items-center gap-1.5"
            :disabled="debugLoading || !errorStatus"
            @click="toggleDebug"
          >
            <Icon v-if="debugLoading" icon="mdi:loading" class="w-4 h-4 animate-spin" />
            <Icon v-else icon="mdi:bug-outline" class="w-4 h-4" />
            {{
              debugLoading
                ? t("tabs.operator_dashboard.debug_toggling")
                : t("tabs.operator_dashboard.debug_toggle_button")
            }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
