<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ModuleInfo, ModuleActionResponse } from "@/api/types";

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
    // Reset selection if no longer in available list
    if (selectedModule.value && !available.value.includes(selectedModule.value)) {
      selectedModule.value = "";
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to fetch modules";
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
      actionError.value = res.error ?? "Unload failed";
    }
  } catch (e: unknown) {
    actionError.value = e instanceof Error ? e.message : "Unload failed";
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
      actionError.value = res.error ?? "Load failed";
    }
  } catch (e: unknown) {
    actionError.value = e instanceof Error ? e.message : "Load failed";
  } finally {
    pendingModule.value = null;
    await fetchModules();
  }
}

onMounted(fetchModules);
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-1">
      <div class="flex items-center gap-2">
        <Icon icon="mdi:puzzle-outline" class="w-5 h-5 text-violet-400" />
        <h2 class="text-xl font-bold">Module Control</h2>
      </div>
      <button
        class="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
        :disabled="loading"
        @click="fetchModules"
      >
        <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': loading }" />
        Refresh
      </button>
    </div>
    <p class="text-muted-foreground text-sm mb-6">
      Load and unload bot modules at runtime. Changes take effect immediately but do not persist across restarts.
    </p>

    <!-- Error -->
    <div v-if="error" class="text-destructive text-sm py-2 mb-4">{{ error }}</div>

    <!-- Action error -->
    <div
      v-if="actionError"
      class="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded px-4 py-3 text-destructive text-sm mb-4"
    >
      <Icon icon="mdi:alert-circle-outline" class="w-4 h-4 flex-shrink-0" />
      {{ actionError }}
    </div>

    <!-- Loaded modules table -->
    <div class="border border-border rounded overflow-hidden mb-6">
      <div class="bg-muted/50 border-b border-border px-4 py-2 flex items-center gap-2">
        <Icon icon="mdi:check-circle-outline" class="w-4 h-4 text-emerald-400" />
        <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Loaded Modules</span>
        <span class="ml-auto text-xs text-muted-foreground">{{ modules.length }} loaded</span>
      </div>

      <div v-if="loading && modules.length === 0" class="flex items-center gap-2 text-muted-foreground text-sm px-4 py-4">
        <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
        Loading…
      </div>

      <div v-else-if="modules.length === 0" class="text-muted-foreground text-sm px-4 py-4">
        No modules loaded or bot unreachable.
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
                  protected
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
                Unload
              </button>
              <span v-else class="text-xs text-muted-foreground/50 px-3 py-1">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Load from available modules -->
    <div class="border border-border rounded px-4 py-4">
      <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <Icon icon="mdi:plus-circle-outline" class="w-3.5 h-3.5" />
        Load Module
      </p>

      <div v-if="available.length === 0" class="text-muted-foreground text-sm">
        {{ loading ? "…" : "All available modules are already loaded." }}
      </div>

      <div v-else class="flex gap-2">
        <select
          v-model="selectedModule"
          class="flex-1 rounded border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
          :disabled="pendingModule !== null"
        >
          <option value="" disabled>Select a module…</option>
          <option v-for="name in available" :key="name" :value="name">{{ name }}</option>
        </select>
        <button
          class="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
          :disabled="!selectedModule || pendingModule !== null"
          @click="load"
        >
          <Icon v-if="pendingModule !== null" icon="mdi:loading" class="w-4 h-4 animate-spin inline mr-1" />
          Load
        </button>
      </div>
    </div>
  </div>
</template>
