<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { onMounted, ref, watch } from "vue";
import { api } from "@/api/client";
import type { BotGuildInfo, ModuleActionResponse, ModuleInfo, SyncCommandsResponse } from "@/api/types";
import { useI18n } from "@/i18n";

const { t } = useI18n();

// ── Sub-tab ──────────────────────────────────────────────────────────────────

type SubTab = "modules" | "sync";
const activeTab = ref<SubTab>("modules");

// ── Modules tab ───────────────────────────────────────────────────────────────

const modules = ref<ModuleInfo[]>([]);
const available = ref<string[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const actionError = ref<string | null>(null);
const selectedModule = ref("");
const pendingModule = ref<string | null>(null);

async function fetchModules() {
  if (loading.value) return;
  loading.value = true;
  error.value = null;
  try {
    const res = await api.get<{ modules: ModuleInfo[]; available: string[]; status: string }>("/operator/modules");
    modules.value = res.modules;
    available.value = res.available ?? [];
    if (selectedModule.value && !available.value.includes(selectedModule.value)) {
      selectedModule.value = "";
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
}

async function unload(name: string) {
  pendingModule.value = name;
  actionError.value = null;
  try {
    const res = await api.post<ModuleActionResponse>(`/operator/modules/${encodeURIComponent(name)}/unload`, {});
    if (!res.success) {
      actionError.value = res.error ?? t("common.save_failed");
    }
  } catch (e: unknown) {
    actionError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    pendingModule.value = null;
    await fetchModules();
  }
}

async function load() {
  const name = selectedModule.value;
  if (!name) return;
  pendingModule.value = name;
  actionError.value = null;
  try {
    const res = await api.post<ModuleActionResponse>(`/operator/modules/${encodeURIComponent(name)}/load`, {});
    if (res.success) {
      selectedModule.value = "";
    } else {
      actionError.value = res.error ?? t("common.save_failed");
    }
  } catch (e: unknown) {
    actionError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    pendingModule.value = null;
    await fetchModules();
  }
}

// ── Command Sync tab ──────────────────────────────────────────────────────────

type SyncMode = "global" | "local" | "copy" | "clear";

const syncMode = ref<SyncMode>("global");
const syncGuildId = ref("");
const syncLoading = ref(false);
const syncMessage = ref<string | null>(null);
const syncError = ref<string | null>(null);
const guilds = ref<BotGuildInfo[]>([]);
const guildsLoading = ref(false);

const needsGuild = (mode: SyncMode) => mode !== "global";

async function fetchGuilds() {
  if (guildsLoading.value || guilds.value.length > 0) return;
  guildsLoading.value = true;
  try {
    const res = await api.get<{ guilds: BotGuildInfo[] }>("/operator/guilds");
    guilds.value = res.guilds;
  } catch {
    // silently ignore — guild list is optional convenience for global sync
  } finally {
    guildsLoading.value = false;
  }
}

watch(activeTab, (tab) => {
  if (tab === "sync") fetchGuilds();
});

watch(syncMode, (mode) => {
  if (!needsGuild(mode)) syncGuildId.value = "";
  else if (guilds.value.length === 0) fetchGuilds();
});

async function triggerSync() {
  if (needsGuild(syncMode.value) && !syncGuildId.value) return;
  syncLoading.value = true;
  syncMessage.value = null;
  syncError.value = null;
  try {
    const body: { mode: SyncMode; guild_ids?: string[] } = { mode: syncMode.value };
    if (syncGuildId.value) body.guild_ids = [syncGuildId.value];
    const res = await api.post<SyncCommandsResponse>("/operator/sync-commands", body);
    if (res.success) {
      syncMessage.value =
        syncMode.value === "clear"
          ? t("tabs.operator_modules.sync_cleared")
          : t("tabs.operator_modules.sync_success", { count: res.synced_count ?? 0 });
    } else {
      syncError.value = res.error ?? t("common.save_failed");
    }
  } catch (e: unknown) {
    syncError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    syncLoading.value = false;
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(fetchModules);
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center gap-2 mb-1">
      <Icon icon="mdi:puzzle-outline" class="w-5 h-5 text-violet-400" />
      <h2 class="text-xl font-bold">{{ t("tabs.operator_modules.title") }}</h2>
    </div>
    <p class="text-muted-foreground text-sm mb-4">{{ t("tabs.operator_modules.desc") }}</p>

    <!-- Sub-tab bar -->
    <div class="subtab-bar">
      <button :class="['subtab-btn', { active: activeTab === 'modules' }]" @click="activeTab = 'modules'">
        <Icon icon="mdi:puzzle-outline" />
        {{ t("tabs.operator_modules.tab_modules") }}
      </button>
      <button
        :class="['subtab-btn', { active: activeTab === 'sync' }]"
        @click="activeTab = 'sync'"
      >
        <Icon icon="mdi:sync" />
        {{ t("tabs.operator_modules.tab_sync") }}
      </button>
    </div>

    <!-- ── Modules sub-tab ── -->
    <template v-if="activeTab === 'modules'">
      <div class="flex justify-end mb-4">
        <button
          class="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
          :disabled="loading"
          @click="fetchModules"
        >
          <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          {{ t("common.refresh") }}
        </button>
      </div>

      <div v-if="error" class="text-destructive text-sm py-2 mb-4">{{ error }}</div>

      <div
        v-if="actionError"
        class="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded px-4 py-3 text-destructive text-sm mb-4"
      >
        <Icon icon="mdi:alert-circle-outline" class="w-4 h-4 flex-shrink-0" />
        {{ actionError }}
      </div>

      <div class="border border-border rounded overflow-hidden mb-6">
        <div class="bg-muted/50 border-b border-border px-4 py-2 flex items-center gap-2">
          <Icon icon="mdi:check-circle-outline" class="w-4 h-4 text-emerald-400" />
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {{ t("tabs.operator_modules.loaded_modules") }}
          </span>
          <span class="ml-auto text-xs text-muted-foreground">
            {{ t("tabs.operator_modules.loaded_count", { count: modules.length }) }}
          </span>
        </div>

        <div
          v-if="loading && modules.length === 0"
          class="flex items-center gap-2 text-muted-foreground text-sm px-4 py-4"
        >
          <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
          {{ t("tabs.operator_modules.loading") }}
        </div>
        <div v-else-if="modules.length === 0" class="text-muted-foreground text-sm px-4 py-4">
          {{ t("tabs.operator_modules.empty") }}
        </div>
        <table v-else class="w-full text-sm">
          <tbody>
            <tr
              v-for="mod in modules"
              :key="mod.name"
              class="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
            >
              <td class="px-4 py-2.5">
                <div class="flex items-center gap-2 font-mono text-sm">
                  {{ mod.name }}
                  <span
                    v-if="mod.protected"
                    class="inline-flex items-center gap-1 text-xs text-amber-400/80 bg-amber-400/10 border border-amber-400/20 rounded px-1.5 py-0.5"
                  >
                    <Icon icon="mdi:lock-outline" class="w-3 h-3" />
                    {{ t("tabs.operator_modules.protected") }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  v-if="!mod.protected"
                  class="px-3 py-1 rounded text-xs font-medium bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive/20 transition-colors disabled:opacity-40"
                  :disabled="pendingModule === mod.name"
                  @click="unload(mod.name)"
                >
                  <Icon
                    v-if="pendingModule === mod.name"
                    icon="mdi:loading"
                    class="w-3 h-3 animate-spin inline mr-1"
                  />
                  {{ t("tabs.operator_modules.unload") }}
                </button>
                <span v-else class="text-xs text-muted-foreground/50 px-3 py-1">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="border border-border rounded px-4 py-4">
        <p
          class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5"
        >
          <Icon icon="mdi:plus-circle-outline" class="w-3.5 h-3.5" />
          {{ t("tabs.operator_modules.load_section") }}
        </p>
        <div v-if="available.length === 0" class="text-muted-foreground text-sm">
          {{ loading ? "…" : t("tabs.operator_modules.all_loaded") }}
        </div>
        <div v-else class="flex gap-2">
          <select
            v-model="selectedModule"
            class="flex-1 rounded border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
            :disabled="pendingModule !== null"
          >
            <option value="" disabled>{{ t("tabs.operator_modules.select") }}</option>
            <option v-for="name in available" :key="name" :value="name">{{ name }}</option>
          </select>
          <button
            class="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
            :disabled="!selectedModule || pendingModule !== null"
            @click="load"
          >
            <Icon v-if="pendingModule !== null" icon="mdi:loading" class="w-4 h-4 animate-spin inline mr-1" />
            {{ t("tabs.operator_modules.load") }}
          </button>
        </div>
      </div>
    </template>

    <!-- ── Command Sync sub-tab ── -->
    <template v-else-if="activeTab === 'sync'">
      <div class="mb-4">
        <p class="text-sm text-muted-foreground">{{ t("tabs.operator_modules.sync_desc") }}</p>
      </div>

      <div class="bg-card border border-border rounded overflow-hidden">
        <div class="bg-muted/50 border-b border-border px-4 py-2.5 flex items-center gap-2">
          <Icon icon="mdi:sync" class="w-4 h-4 text-muted-foreground" />
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {{ t("tabs.operator_modules.sync_title") }}
          </span>
        </div>
        <div class="px-4 py-4 space-y-4">
          <!-- Mode selector -->
          <div>
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              {{ t("tabs.operator_modules.sync_mode_label") }}
            </p>
            <div class="space-y-1.5">
              <label
                v-for="mode in ['global', 'local', 'copy', 'clear'] as SyncMode[]"
                :key="mode"
                class="flex items-start gap-2.5 cursor-pointer"
              >
                <input v-model="syncMode" type="radio" :value="mode" class="mt-0.5 flex-shrink-0" />
                <span class="text-sm">{{ t(`tabs.operator_modules.sync_mode_${mode}`) }}</span>
              </label>
            </div>
          </div>

          <!-- Guild selector for guild-specific modes -->
          <div v-if="needsGuild(syncMode)">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              {{ t("tabs.operator_modules.sync_guild_label") }}
            </p>
            <select
              v-model="syncGuildId"
              class="w-full rounded border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
              :disabled="guildsLoading"
            >
              <option value="" disabled>
                {{ guildsLoading ? t("common.loading") : t("tabs.operator_modules.sync_guild_placeholder") }}
              </option>
              <option v-for="g in guilds" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </div>

          <!-- Feedback -->
          <div v-if="syncMessage" class="flex items-center gap-2 text-emerald-400 text-sm">
            <Icon icon="mdi:check-circle-outline" class="w-4 h-4 flex-shrink-0" />
            {{ syncMessage }}
          </div>
          <p v-if="syncError" class="text-destructive text-sm">{{ syncError }}</p>

          <!-- Trigger button -->
          <button
            class="px-4 py-2 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors flex items-center gap-1.5"
            :disabled="syncLoading || (needsGuild(syncMode) && !syncGuildId)"
            @click="triggerSync"
          >
            <Icon v-if="syncLoading" icon="mdi:loading" class="w-4 h-4 animate-spin" />
            <Icon v-else icon="mdi:sync" class="w-4 h-4" />
            {{
              syncLoading ? t("tabs.operator_modules.sync_syncing") : t("tabs.operator_modules.sync_button")
            }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.subtab-bar {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--color-border, #333);
  padding-bottom: 0;
}

.subtab-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.9rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: var(--color-text-muted, #888);
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: -1px;
  transition: color 0.15s;
}

.subtab-btn:hover {
  color: var(--color-text, #fff);
}

.subtab-btn.active {
  color: var(--color-accent, #7289da);
  border-bottom-color: var(--color-accent, #7289da);
}
</style>
