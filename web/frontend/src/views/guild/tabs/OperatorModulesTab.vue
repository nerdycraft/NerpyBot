<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ModuleInfo, ModuleActionResponse } from "@/api/types";

const modules = ref<ModuleInfo[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const actionError = ref<string | null>(null);
const loadName = ref("");
const pendingModule = ref<string | null>(null);

async function fetchModules() {
  if (loading.value) return;
  loading.value = true;
  error.value = null;
  try {
    const res = await api.get<{ modules: ModuleInfo[]; status: string }>("/operator/modules");
    modules.value = res.modules;
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
    const res = await api.post<ModuleActionResponse>(`/operator/modules/${name}/unload`, {});
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
  const name = loadName.value.trim();
  if (!name) return;
  pendingModule.value = name;
  actionError.value = null;
  try {
    const res = await api.post<ModuleActionResponse>(`/operator/modules/${name}/load`, {});
    if (res.success) {
      loadName.value = "";
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
            <td class="px-4 py-2.5 font-mono text-sm">{{ mod.name }}</td>
            <td class="px-4 py-2.5 text-right">
              <button
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
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Load by name -->
    <div class="border border-border rounded px-4 py-4">
      <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <Icon icon="mdi:plus-circle-outline" class="w-3.5 h-3.5" />
        Load Module
      </p>
      <div class="flex gap-2">
        <input
          v-model="loadName"
          type="text"
          placeholder="module name (e.g. reminder)"
          class="flex-1 rounded border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          @keydown.enter="load"
        />
        <button
          class="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
          :disabled="!loadName.trim() || pendingModule !== null"
          @click="load"
        >
          <Icon v-if="pendingModule !== null" icon="mdi:loading" class="w-4 h-4 animate-spin inline mr-1" />
          Load
        </button>
      </div>
    </div>
  </div>
</template>
