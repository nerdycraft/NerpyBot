<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/api/client";
import type {
  CraftingBoardSchema,
  CraftingOrderSchema,
  CraftingRoleMappingSchema,
  CraftingRoleMappingUpdate,
  DiscordRole,
} from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import { type I18nKey, useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();

const { t, locale } = useI18n();
const { fetchChannels, fetchRoles, channelName, roleName } = useGuildEntities(props.guildId);

const boards = ref<CraftingBoardSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const orders = ref<CraftingOrderSchema[]>([]);
const ordersLoading = ref(false);
const ordersError = ref<string | null>(null);
const statusFilter = ref<string>("");

// ── Role Mappings ──
const mappings = ref<CraftingRoleMappingSchema[]>([]);
const mappingsLoading = ref(false);
const mappingsError = ref<string | null>(null);
const opError = ref<string | null>(null);

const allRoles = ref<DiscordRole[]>([]);
const newMappingRoleId = ref("");
const newMappingProfessionId = ref<number | "">("");
const addingMapping = ref(false);
const editingMappingId = ref<number | null>(null);
const editMappingProfessionId = ref<number | "">("");

const PROFESSIONS: { id: number; labelKey: I18nKey }[] = [
  { id: 164, labelKey: "tabs.wow_crafting.profession.blacksmithing" },
  { id: 165, labelKey: "tabs.wow_crafting.profession.leatherworking" },
  { id: 197, labelKey: "tabs.wow_crafting.profession.tailoring" },
  { id: 202, labelKey: "tabs.wow_crafting.profession.engineering" },
  { id: 333, labelKey: "tabs.wow_crafting.profession.enchanting" },
  { id: 171, labelKey: "tabs.wow_crafting.profession.alchemy" },
  { id: 773, labelKey: "tabs.wow_crafting.profession.inscription" },
  { id: 755, labelKey: "tabs.wow_crafting.profession.jewelcrafting" },
  { id: 185, labelKey: "tabs.wow_crafting.profession.cooking" },
];

function professionLabel(professionId: number, fallback: string): string {
  const p = PROFESSIONS.find((x) => x.id === professionId);
  return p ? t(p.labelKey) : fallback;
}

const availableRoles = computed(() => {
  const usedRoleIds = new Set(mappings.value.map((m) => m.role_id));
  return allRoles.value.filter((r) => !usedRoleIds.has(r.id));
});

const availableProfessions = computed(() => {
  const usedProfessionIds = new Set(mappings.value.map((m) => m.profession_id));
  return PROFESSIONS.filter((p) => !usedProfessionIds.has(p.id));
});

function availableProfessionsForEdit(currentProfessionId: number) {
  const usedProfessionIds = new Set(
    mappings.value.filter((m) => m.profession_id !== currentProfessionId).map((m) => m.profession_id),
  );
  return PROFESSIONS.filter((p) => !usedProfessionIds.has(p.id));
}

const orderDateFormatter = computed(() => new Intl.DateTimeFormat(locale.current, { dateStyle: "short" }));

const STATUS_LABEL_KEYS: Record<string, I18nKey> = {
  "": "tabs.wow_crafting.status.all",
  open: "tabs.wow_crafting.status.open",
  in_progress: "tabs.wow_crafting.status.in_progress",
  completed: "tabs.wow_crafting.status.completed",
  cancelled: "tabs.wow_crafting.status.cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  open: "text-yellow-400",
  in_progress: "text-blue-400",
  completed: "text-green-400",
  cancelled: "text-muted-foreground",
};

async function fetchOrders() {
  ordersLoading.value = true;
  ordersError.value = null;
  try {
    const params = statusFilter.value ? `?order_status=${statusFilter.value}` : "";
    orders.value = await api.get<CraftingOrderSchema[]>(`/guilds/${props.guildId}/wow/crafting-orders${params}`);
  } catch (e: unknown) {
    ordersError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    ordersLoading.value = false;
  }
}

async function fetchMappings() {
  mappingsLoading.value = true;
  mappingsError.value = null;
  try {
    mappings.value = await api.get<CraftingRoleMappingSchema[]>(`/guilds/${props.guildId}/wow/crafting-role-mappings`);
  } catch (e: unknown) {
    mappingsError.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    mappingsLoading.value = false;
  }
}

async function addMapping() {
  if (!newMappingRoleId.value || newMappingProfessionId.value === "") return;
  opError.value = null;
  addingMapping.value = true;
  try {
    const created = await api.post<CraftingRoleMappingSchema>(`/guilds/${props.guildId}/wow/crafting-role-mappings`, {
      role_id: newMappingRoleId.value,
      profession_id: newMappingProfessionId.value,
    });
    mappings.value.push(created);
    newMappingRoleId.value = "";
    newMappingProfessionId.value = "";
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    addingMapping.value = false;
  }
}

async function updateMapping(mappingId: number) {
  if (editMappingProfessionId.value === "") return;
  opError.value = null;
  try {
    const body: CraftingRoleMappingUpdate = { profession_id: editMappingProfessionId.value as number };
    const updated = await api.put<CraftingRoleMappingSchema>(
      `/guilds/${props.guildId}/wow/crafting-role-mappings/${mappingId}`,
      body,
    );
    const idx = mappings.value.findIndex((m) => m.id === mappingId);
    if (idx !== -1) mappings.value[idx] = updated;
    editingMappingId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  }
}

async function deleteMapping(mappingId: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/wow/crafting-role-mappings/${mappingId}`);
    mappings.value = mappings.value.filter((m) => m.id !== mappingId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}

onMounted(async () => {
  void fetchChannels();
  void fetchRoles();

  try {
    const config = await api.get<{ crafting_boards: CraftingBoardSchema[] }>(`/guilds/${props.guildId}/wow`);
    boards.value = config.crafting_boards;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }

  const rolesData = await api
    .get<{ roles: { id: string; name: string }[] }>(`/guilds/${props.guildId}/discord/roles`)
    .catch(() => ({ roles: [] }));
  allRoles.value = rolesData.roles;

  await Promise.all([fetchOrders(), fetchMappings()]);
});

watch(statusFilter, fetchOrders);
</script>

<template>
  <div class="space-y-8">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.wow_crafting.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.wow_crafting.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else class="space-y-8">
      <!-- Board Config -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">{{ t("tabs.wow_crafting.board") }}</h3>
        <p v-if="boards.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.wow_crafting.no_board") }}</p>
        <div
          v-for="cb in boards"
          :key="cb.id"
          class="bg-card border border-border rounded px-4 py-3"
        >
          <div class="text-sm font-medium">#{{ channelName(cb.channel_id) }}</div>
          <div v-if="cb.description" class="text-xs text-muted-foreground mt-1">{{ cb.description }}</div>
        </div>
      </div>

      <!-- Role Mappings -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">{{ t("tabs.wow_crafting.role_mappings") }}</h3>
        <p class="text-muted-foreground text-xs">{{ t("tabs.wow_crafting.role_mappings_desc") }}</p>

        <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
        <div v-if="mappingsLoading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
        <p v-else-if="mappingsError" class="text-destructive text-sm">{{ mappingsError }}</p>

        <div v-else class="space-y-1.5">
          <div
            v-for="m in mappings"
            :key="m.id"
            class="flex items-center gap-3 bg-card border border-border rounded px-3 py-2 text-sm group"
          >
            <template v-if="editingMappingId === m.id">
              <span class="text-muted-foreground flex-shrink-0">@{{ roleName(m.role_id) }} →</span>
              <select
                v-model="editMappingProfessionId"
                class="bg-input border border-border rounded px-2 py-1 text-sm flex-1 min-w-[140px]"
              >
                <option v-for="p in availableProfessionsForEdit(m.profession_id)" :key="p.id" :value="p.id">{{ t(p.labelKey) }}</option>
              </select>
              <button class="text-xs text-primary hover:text-primary/80 flex-shrink-0" @click="updateMapping(m.id)">{{ t("common.save") }}</button>
              <button class="text-xs text-muted-foreground hover:text-foreground flex-shrink-0" @click="editingMappingId = null">×</button>
            </template>
            <template v-else>
              <span class="flex-1">@{{ roleName(m.role_id) }} → {{ professionLabel(m.profession_id, m.profession_name) }}</span>
              <button
                class="text-xs text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                @click="editingMappingId = m.id; editMappingProfessionId = m.profession_id"
              >{{ t("common.edit") }}</button>
              <button
                class="text-xs text-destructive hover:text-destructive/80 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                @click="deleteMapping(m.id)"
              >
                <Icon icon="mdi:close" class="w-4 h-4" />
              </button>
            </template>
          </div>
          <p v-if="mappings.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.wow_crafting.no_mappings") }}</p>
        </div>

        <!-- Add mapping -->
        <div class="flex flex-wrap gap-2 items-end pt-1">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium flex items-center gap-1.5">
              {{ t("tabs.wow_crafting.role_label") }}
              <InfoTooltip :text="t('tabs.wow_crafting.role_tooltip')" />
            </label>
            <select
              v-model="newMappingRoleId"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm min-w-[160px]"
            >
              <option value="">{{ t("tabs.wow_crafting.select_role") }}</option>
              <option v-for="r in availableRoles" :key="r.id" :value="r.id">@{{ r.name }}</option>
            </select>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium flex items-center gap-1.5">
              {{ t("tabs.wow_crafting.profession_label") }}
              <InfoTooltip :text="t('tabs.wow_crafting.profession_tooltip')" />
            </label>
            <select
              v-model="newMappingProfessionId"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm min-w-[160px]"
            >
              <option value="">{{ t("tabs.wow_crafting.select_profession") }}</option>
              <option v-for="p in availableProfessions" :key="p.id" :value="p.id">{{ t(p.labelKey) }}</option>
            </select>
          </div>
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
            :disabled="!newMappingRoleId || newMappingProfessionId === '' || addingMapping"
            @click="addMapping"
          >{{ t("common.add") }}</button>
        </div>
      </div>

      <!-- Crafting Orders -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold">{{ t("tabs.wow_crafting.orders") }}</h3>
          <div class="flex items-center gap-1 rounded-md border border-border p-0.5 bg-muted text-xs">
            <button
              v-for="(labelKey, value) in STATUS_LABEL_KEYS"
              :key="value"
              :class="[
                'px-2.5 py-1 rounded transition-colors',
                statusFilter === value
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="statusFilter = value"
            >
              {{ t(labelKey) }}
            </button>
          </div>
        </div>

        <div v-if="ordersLoading" class="text-muted-foreground text-sm">{{ t("tabs.wow_crafting.loading_orders") }}</div>
        <p v-else-if="ordersError" class="text-destructive text-sm">{{ ordersError }}</p>
        <p v-else-if="orders.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.wow_crafting.no_orders") }}</p>
        <div v-else class="space-y-2">
          <div
            v-for="order in orders"
            :key="order.id"
            class="bg-card border border-border rounded px-4 py-3 flex items-center gap-4"
          >
            <img
              v-if="order.icon_url"
              :src="order.icon_url"
              :alt="order.item_name"
              class="w-8 h-8 rounded object-cover flex-shrink-0"
            />
            <div
              v-else
              class="w-8 h-8 rounded bg-muted flex items-center justify-center flex-shrink-0"
            >
              <Icon icon="mdi:sword" class="w-4 h-4 text-muted-foreground" />
            </div>

            <div class="flex-1 min-w-0">
              <div class="font-medium text-sm truncate">{{ order.item_name }}</div>
              <div class="text-xs text-muted-foreground space-x-2">
                <span>{{ t("tabs.wow_crafting.order_by", { name: order.creator_name ?? order.creator_id ?? "" }) }}</span>
                <span v-if="order.crafter_name ?? order.crafter_id">
                  · {{ t("tabs.wow_crafting.order_crafter", { name: order.crafter_name ?? order.crafter_id ?? "" }) }}
                </span>
              </div>
              <div v-if="order.notes" class="text-xs text-muted-foreground truncate mt-0.5">{{ order.notes }}</div>
            </div>

            <div class="flex items-center gap-3 text-xs flex-shrink-0">
              <span :class="STATUS_COLORS[order.status] ?? 'text-muted-foreground'" class="font-medium">
                {{ STATUS_LABEL_KEYS[order.status] ? t(STATUS_LABEL_KEYS[order.status]!) : order.status }}
              </span>
              <span class="text-muted-foreground">{{ orderDateFormatter.format(new Date(order.create_date)) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
