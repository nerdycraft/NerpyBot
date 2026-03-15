<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { onMounted, ref, watch } from "vue";
import { api } from "@/api/client";
import type {
  RecipeCacheBrowseResponse,
  RecipeCacheEntry,
  RecipeCacheProfession,
  RecipeSyncResponse,
  RecipeSyncStatusResponse,
} from "@/api/types";
import { useI18n } from "@/i18n";

const { t } = useI18n();

// ── Sub-tab ──────────────────────────────────────────────────────────────────

type SubTab = "sync" | "browse";
const activeTab = ref<SubTab>("sync");

// ── Sync tab ─────────────────────────────────────────────────────────────────

const counts = ref<Record<string, number>>({});
const statusLoading = ref(false);
const syncLoading = ref(false);
const syncError = ref<string | null>(null);
const syncMessage = ref<string | null>(null);

async function fetchStatus() {
  if (statusLoading.value) return;
  statusLoading.value = true;
  syncError.value = null;
  try {
    const res = await api.get<RecipeSyncStatusResponse>("/operator/recipe-sync/status");
    counts.value = res.counts ?? {};
  } catch (e: unknown) {
    syncError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    statusLoading.value = false;
  }
}

async function triggerSync() {
  syncLoading.value = true;
  syncMessage.value = null;
  syncError.value = null;
  try {
    const res = await api.post<RecipeSyncResponse>("/operator/recipe-sync", {});
    if (res.queued) {
      syncMessage.value = t("tabs.operator_recipe_sync.sync_queued");
      setTimeout(fetchStatus, 5000);
    } else {
      syncError.value = res.error ?? t("tabs.operator_recipe_sync.sync_failed");
    }
  } catch (e: unknown) {
    syncError.value = e instanceof Error ? e.message : t("tabs.operator_recipe_sync.sync_failed");
  } finally {
    syncLoading.value = false;
  }
}

// ── Browse tab ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

const browseType = ref<string>("");
const browseProfession = ref<number | "">("");
const browseExpansion = ref<string>("");
const browsePage = ref(0);

const browseLoading = ref(false);
const browseError = ref<string | null>(null);
const browseRecipes = ref<RecipeCacheEntry[]>([]);
const browseProfessions = ref<RecipeCacheProfession[]>([]);
const browseExpansions = ref<string[]>([]);
const browseTotal = ref(0);

async function fetchBrowse() {
  browseLoading.value = true;
  browseError.value = null;
  try {
    const params: Record<string, string | number> = {
      offset: browsePage.value * PAGE_SIZE,
      limit: PAGE_SIZE,
    };
    if (browseType.value) params.recipe_type = browseType.value;
    if (browseProfession.value !== "") params.profession_id = browseProfession.value;
    if (browseExpansion.value) params.expansion = browseExpansion.value;

    const qs = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
    const res = await api.get<RecipeCacheBrowseResponse>(`/operator/recipe-cache?${qs}`);
    browseRecipes.value = res.recipes;
    // Dropdown lists are only returned on offset=0 (filter change / first load).
    // On subsequent pages the server returns empty arrays — keep existing values.
    if (res.professions.length) browseProfessions.value = res.professions;
    if (res.expansions.length) browseExpansions.value = res.expansions;
    browseTotal.value = res.total;
  } catch (e: unknown) {
    browseError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    browseLoading.value = false;
  }
}

function resetAndFetch() {
  browsePage.value = 0;
  fetchBrowse();
}

watch([browseType, browseProfession, browseExpansion], resetAndFetch);
watch(browsePage, fetchBrowse);

watch(activeTab, (tab) => {
  if (tab === "browse" && browseRecipes.value.length === 0 && !browseLoading.value) {
    fetchBrowse();
  }
});

const browseFrom = () => (browseTotal.value === 0 ? 0 : browsePage.value * PAGE_SIZE + 1);
const browseTo = () => Math.min((browsePage.value + 1) * PAGE_SIZE, browseTotal.value);
const totalPages = () => Math.ceil(browseTotal.value / PAGE_SIZE);

onMounted(fetchStatus);
</script>

<template>
  <div class="tab-content">
    <h2 class="tab-title">{{ t("tabs.operator_recipe_sync.title") }}</h2>
    <p class="tab-desc">{{ t("tabs.operator_recipe_sync.desc") }}</p>

    <!-- Sub-tab switcher -->
    <div class="subtab-bar">
      <button :class="['subtab-btn', { active: activeTab === 'sync' }]" @click="activeTab = 'sync'">
        <Icon icon="mdi:sync" />
        {{ t("tabs.operator_recipe_sync.tab_sync") }}
      </button>
      <button :class="['subtab-btn', { active: activeTab === 'browse' }]" @click="activeTab = 'browse'">
        <Icon icon="mdi:magnify" />
        {{ t("tabs.operator_recipe_sync.tab_browse") }}
      </button>
    </div>

    <!-- ── Sync tab ── -->
    <template v-if="activeTab === 'sync'">
      <div class="card">
        <div class="card-header">
          <Icon icon="mdi:book-open-outline" class="card-icon" />
          <span>{{ t("tabs.operator_recipe_sync.cache_stats") }}</span>
          <button class="btn-icon" :disabled="statusLoading" @click="fetchStatus" :title="t('common.refresh')">
            <Icon icon="mdi:refresh" :class="{ spinning: statusLoading }" />
          </button>
        </div>

        <div v-if="syncError" class="error-banner">{{ syncError }}</div>

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
    </template>

    <!-- ── Browse tab ── -->
    <template v-else>
      <div class="filter-bar">
        <select v-model="browseType" class="filter-select">
          <option value="">{{ t("tabs.operator_recipe_sync.browse_type_all") }}</option>
          <option value="crafted">{{ t("tabs.operator_recipe_sync.browse_type_crafted") }}</option>
          <option value="housing">{{ t("tabs.operator_recipe_sync.browse_type_housing") }}</option>
        </select>

        <select v-model="browseProfession" class="filter-select">
          <option value="">{{ t("tabs.operator_recipe_sync.browse_profession_all") }}</option>
          <option v-for="p in browseProfessions" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>

        <select v-model="browseExpansion" class="filter-select">
          <option value="">{{ t("tabs.operator_recipe_sync.browse_expansion_all") }}</option>
          <option v-for="exp in browseExpansions" :key="exp" :value="exp">{{ exp }}</option>
        </select>
      </div>

      <div v-if="browseError" class="error-banner">{{ browseError }}</div>

      <div v-if="browseLoading && browseRecipes.length === 0" class="loading-text">{{ t("common.loading") }}</div>
      <div v-else-if="!browseLoading && browseRecipes.length === 0" class="empty-text">
        {{ t("tabs.operator_recipe_sync.browse_empty") }}
      </div>

      <div v-else class="recipe-table-wrap">
        <table class="recipe-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Profession</th>
              <th>Type</th>
              <th>Class</th>
              <th>Expansion</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in browseRecipes" :key="r.recipe_id" :class="{ 'row-loading': browseLoading }">
              <td>
                <a v-if="r.wowhead_url" :href="r.wowhead_url" target="_blank" rel="noopener" class="item-link">
                  {{ r.item_name }}
                </a>
                <span v-else>{{ r.item_name }}</span>
              </td>
              <td>{{ r.profession_name }}</td>
              <td><span :class="['type-badge', `type-${r.recipe_type}`]">{{ r.recipe_type }}</span></td>
              <td class="muted">{{ [r.item_class_name, r.item_subclass_name].filter(Boolean).join(" / ") || "—" }}</td>
              <td class="muted">{{ r.expansion_name ?? "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="browseTotal > PAGE_SIZE" class="pagination">
        <button class="page-btn" :disabled="browsePage === 0" @click="browsePage--">
          <Icon icon="mdi:chevron-left" />
        </button>
        <span class="page-info">
          {{ t("tabs.operator_recipe_sync.browse_showing", { from: browseFrom(), to: browseTo(), total: browseTotal }) }}
        </span>
        <button class="page-btn" :disabled="browsePage >= totalPages() - 1" @click="browsePage++">
          <Icon icon="mdi:chevron-right" />
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tab-content {
  padding: 1rem;
  max-width: 900px;
}

.tab-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.tab-desc {
  color: var(--color-text-muted, #888);
  margin-bottom: 1rem;
}

/* Sub-tab bar */
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

/* Cards */
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

/* Browse */
.filter-bar {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.filter-select {
  padding: 0.35rem 0.6rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: var(--color-surface, #1e1e1e);
  color: var(--color-text, #fff);
  font-size: 0.875rem;
  cursor: pointer;
}

.recipe-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
}

.recipe-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.recipe-table th {
  padding: 0.5rem 0.75rem;
  text-align: left;
  font-weight: 600;
  background: var(--color-surface, #1e1e1e);
  color: var(--color-text-muted, #888);
  border-bottom: 1px solid var(--color-border, #333);
  white-space: nowrap;
}

.recipe-table td {
  padding: 0.4rem 0.75rem;
  border-bottom: 1px solid var(--color-border, #333);
}

.recipe-table tr:last-child td {
  border-bottom: none;
}

.recipe-table tr:hover td {
  background: var(--color-surface-hover, rgba(255, 255, 255, 0.03));
}

.row-loading td {
  opacity: 0.5;
}

.item-link {
  color: var(--color-accent, #7289da);
  text-decoration: none;
}

.item-link:hover {
  text-decoration: underline;
}

.muted {
  color: var(--color-text-muted, #888);
}

.type-badge {
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}

.type-crafted {
  background: rgba(114, 137, 218, 0.2);
  color: #7289da;
}

.type-housing {
  background: rgba(67, 181, 129, 0.2);
  color: #43b581;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.page-btn {
  background: none;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  color: var(--color-text, #fff);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 0.25rem;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  font-size: 0.875rem;
  color: var(--color-text-muted, #888);
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
