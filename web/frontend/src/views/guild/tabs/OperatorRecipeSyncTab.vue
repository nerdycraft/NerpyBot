<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { RecipeSyncResponse, RecipeSyncStatusResponse } from "@/api/types";
import { useI18n } from "@/i18n";

const { t } = useI18n();

const counts = ref<Record<string, number>>({});
const statusLoading = ref(false);
const syncLoading = ref(false);
const error = ref<string | null>(null);
const syncMessage = ref<string | null>(null);

async function fetchStatus() {
  if (statusLoading.value) return;
  statusLoading.value = true;
  error.value = null;
  try {
    const res = await api.get<RecipeSyncStatusResponse>("/operator/recipe-sync/status");
    counts.value = res.counts ?? {};
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    statusLoading.value = false;
  }
}

async function triggerSync() {
  syncLoading.value = true;
  syncMessage.value = null;
  error.value = null;
  try {
    const res = await api.post<RecipeSyncResponse>("/operator/recipe-sync", {});
    if (res.queued) {
      syncMessage.value = t("tabs.operator_recipe_sync.sync_queued");
      // Refresh status after a short delay so counts update
      setTimeout(fetchStatus, 5000);
    } else {
      error.value = res.error ?? t("tabs.operator_recipe_sync.sync_failed");
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("tabs.operator_recipe_sync.sync_failed");
  } finally {
    syncLoading.value = false;
  }
}

onMounted(fetchStatus);
</script>

<template>
  <div class="tab-content">
    <h2 class="tab-title">{{ t("tabs.operator_recipe_sync.title") }}</h2>
    <p class="tab-desc">{{ t("tabs.operator_recipe_sync.desc") }}</p>

    <div class="card">
      <div class="card-header">
        <Icon icon="mdi:book-open-outline" class="card-icon" />
        <span>{{ t("tabs.operator_recipe_sync.cache_stats") }}</span>
        <button class="btn-icon" :disabled="statusLoading" @click="fetchStatus" :title="t('common.refresh')">
          <Icon icon="mdi:refresh" :class="{ spinning: statusLoading }" />
        </button>
      </div>

      <div v-if="error" class="error-banner">{{ error }}</div>

      <div v-if="statusLoading && !Object.keys(counts).length" class="loading-text">
        {{ t("common.loading") }}
      </div>
      <div v-else-if="!Object.keys(counts).length" class="empty-text">
        {{ t("tabs.operator_recipe_sync.cache_empty") }}
      </div>
      <div v-else class="stat-grid">
        <div v-for="(count, type) in counts" :key="type" class="stat-row">
          <span class="stat-label">{{ type }}</span>
          <span class="stat-value">{{ count }}</span>
        </div>
      </div>
    </div>

    <div class="card action-card">
      <div class="card-header">
        <Icon icon="mdi:sync" class="card-icon" />
        <span>{{ t("tabs.operator_recipe_sync.sync_title") }}</span>
      </div>
      <p class="card-body-text">{{ t("tabs.operator_recipe_sync.sync_desc") }}</p>

      <div v-if="syncMessage" class="success-banner">{{ syncMessage }}</div>

      <button class="btn-primary" :disabled="syncLoading" @click="triggerSync">
        <Icon v-if="syncLoading" icon="mdi:loading" class="spinning" />
        <Icon v-else icon="mdi:cloud-download-outline" />
        {{ syncLoading ? t("tabs.operator_recipe_sync.syncing") : t("tabs.operator_recipe_sync.sync_button") }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  padding: 1rem;
  max-width: 600px;
}

.tab-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.tab-desc {
  color: var(--color-text-muted, #888);
  margin-bottom: 1.5rem;
}

.card {
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
  margin-bottom: 1rem;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-surface, #1e1e1e);
  font-weight: 600;
  border-bottom: 1px solid var(--color-border, #333);
}

.card-icon {
  font-size: 1.1rem;
  color: var(--color-accent, #7289da);
}

.btn-icon {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted, #888);
  display: flex;
  align-items: center;
  padding: 2px;
}

.btn-icon:hover {
  color: var(--color-text, #fff);
}

.stat-grid {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.9rem;
}

.stat-label {
  text-transform: capitalize;
  color: var(--color-text-muted, #888);
}

.stat-value {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.action-card .card-body-text {
  padding: 0.75rem 1rem 0;
  color: var(--color-text-muted, #888);
  font-size: 0.9rem;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 1rem;
  padding: 0.5rem 1rem;
  background: var(--color-accent, #7289da);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-text,
.empty-text {
  padding: 1rem;
  color: var(--color-text-muted, #888);
  font-size: 0.9rem;
}

.error-banner {
  margin: 0.75rem 1rem;
  padding: 0.5rem 0.75rem;
  background: rgba(220, 50, 50, 0.15);
  border-left: 3px solid #dc3232;
  border-radius: 4px;
  color: #ff6b6b;
  font-size: 0.875rem;
}

.success-banner {
  margin: 0.75rem 1rem;
  padding: 0.5rem 0.75rem;
  background: rgba(67, 181, 129, 0.15);
  border-left: 3px solid #43b581;
  border-radius: 4px;
  color: #43b581;
  font-size: 0.875rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.spinning {
  animation: spin 1s linear infinite;
}
</style>
