<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { CraftingBoardSchema, CraftingOrderSchema, CraftingRoleMappingSchema, DiscordRole } from "@/api/types";
import { useGuildEntities } from "@/composables/useGuildEntities";

const props = defineProps<{ guildId: string }>();

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

const PROFESSIONS: { id: number; name: string }[] = [
  { id: 164, name: "Blacksmithing" },
  { id: 165, name: "Leatherworking" },
  { id: 197, name: "Tailoring" },
  { id: 202, name: "Engineering" },
  { id: 333, name: "Enchanting" },
  { id: 171, name: "Alchemy" },
  { id: 773, name: "Inscription" },
  { id: 755, name: "Jewelcrafting" },
  { id: 185, name: "Cooking" },
];

const STATUS_LABELS: Record<string, string> = {
  "": "All",
  open: "Open",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
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
    const params = statusFilter.value ? `?status_filter=${statusFilter.value}` : "";
    orders.value = await api.get<CraftingOrderSchema[]>(
      `/guilds/${props.guildId}/wow/crafting-orders${params}`,
    );
  } catch (e: unknown) {
    ordersError.value = e instanceof Error ? e.message : "Failed to load orders";
  } finally {
    ordersLoading.value = false;
  }
}

async function fetchMappings() {
  mappingsLoading.value = true;
  mappingsError.value = null;
  try {
    mappings.value = await api.get<CraftingRoleMappingSchema[]>(
      `/guilds/${props.guildId}/wow/crafting-role-mappings`,
    );
  } catch (e: unknown) {
    mappingsError.value = e instanceof Error ? e.message : "Failed to load mappings";
  } finally {
    mappingsLoading.value = false;
  }
}

async function addMapping() {
  if (!newMappingRoleId.value || newMappingProfessionId.value === "") return;
  opError.value = null;
  addingMapping.value = true;
  try {
    const created = await api.post<CraftingRoleMappingSchema>(
      `/guilds/${props.guildId}/wow/crafting-role-mappings`,
      { role_id: newMappingRoleId.value, profession_id: newMappingProfessionId.value },
    );
    mappings.value.push(created);
    newMappingRoleId.value = "";
    newMappingProfessionId.value = "";
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to add mapping";
  } finally {
    addingMapping.value = false;
  }
}

async function deleteMapping(mappingId: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/wow/crafting-role-mappings/${mappingId}`);
    mappings.value = mappings.value.filter((m) => m.id !== mappingId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to delete mapping";
  }
}

onMounted(async () => {
  void fetchChannels();
  void fetchRoles();

  try {
    const config = await api.get<{ crafting_boards: CraftingBoardSchema[] }>(`/guilds/${props.guildId}/wow`);
    boards.value = config.crafting_boards;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }

  const rolesData = await api.get<{ roles: { id: string; name: string }[] }>(`/guilds/${props.guildId}/discord/roles`).catch(() => ({ roles: [] }));
  allRoles.value = rolesData.roles;

  await Promise.all([fetchOrders(), fetchMappings()]);
});

watch(statusFilter, fetchOrders);
</script>

<template>
  <div class="space-y-8">
    <div>
      <h2 class="text-lg font-semibold">Crafting Boards</h2>
      <p class="text-muted-foreground text-sm">Board configuration, role mappings, and orders.</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else class="space-y-8">
      <!-- Board Config -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">Board</h3>
        <p v-if="boards.length === 0" class="text-muted-foreground text-sm">No crafting board configured.</p>
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
        <h3 class="text-sm font-semibold">Role → Profession Mappings</h3>
        <p class="text-muted-foreground text-xs">Map Discord roles to WoW professions so crafters can accept matching orders.</p>

        <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
        <div v-if="mappingsLoading" class="text-muted-foreground text-sm">Loading…</div>
        <p v-else-if="mappingsError" class="text-destructive text-sm">{{ mappingsError }}</p>

        <div v-else class="space-y-1.5">
          <div
            v-for="m in mappings"
            :key="m.id"
            class="flex items-center gap-3 bg-card border border-border rounded px-3 py-2 text-sm group"
          >
            <span class="flex-1">@{{ roleName(m.role_id) }} → {{ m.profession_name }}</span>
            <button
              class="text-xs text-destructive hover:text-destructive/80 opacity-0 group-hover:opacity-100 transition-opacity"
              @click="deleteMapping(m.id)"
            >
              <Icon icon="mdi:close" class="w-4 h-4" />
            </button>
          </div>
          <p v-if="mappings.length === 0" class="text-muted-foreground text-sm">No mappings yet.</p>
        </div>

        <!-- Add mapping -->
        <div class="flex flex-wrap gap-2 items-end pt-1">
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground">Role</label>
            <select
              v-model="newMappingRoleId"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm min-w-[160px]"
            >
              <option value="">Select role…</option>
              <option v-for="r in allRoles" :key="r.id" :value="r.id">@{{ r.name }}</option>
            </select>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground">Profession</label>
            <select
              v-model="newMappingProfessionId"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm min-w-[160px]"
            >
              <option value="">Select profession…</option>
              <option v-for="p in PROFESSIONS" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
            :disabled="!newMappingRoleId || newMappingProfessionId === '' || addingMapping"
            @click="addMapping"
          >Add</button>
        </div>
      </div>

      <!-- Crafting Orders -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold">Orders</h3>
          <div class="flex items-center gap-1 rounded-md border border-border p-0.5 bg-muted text-xs">
            <button
              v-for="(label, value) in STATUS_LABELS"
              :key="value"
              :class="[
                'px-2.5 py-1 rounded transition-colors',
                statusFilter === value
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              ]"
              @click="statusFilter = value"
            >
              {{ label }}
            </button>
          </div>
        </div>

        <div v-if="ordersLoading" class="text-muted-foreground text-sm">Loading orders…</div>
        <p v-else-if="ordersError" class="text-destructive text-sm">{{ ordersError }}</p>
        <p v-else-if="orders.length === 0" class="text-muted-foreground text-sm">No orders found.</p>
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
                <span>by {{ order.creator_name ?? order.creator_id }}</span>
                <span v-if="order.crafter_name ?? order.crafter_id">
                  · crafter: {{ order.crafter_name ?? order.crafter_id }}
                </span>
              </div>
              <div v-if="order.notes" class="text-xs text-muted-foreground truncate mt-0.5">{{ order.notes }}</div>
            </div>

            <div class="flex items-center gap-3 text-xs flex-shrink-0">
              <span :class="STATUS_COLORS[order.status] ?? 'text-muted-foreground'" class="capitalize font-medium">
                {{ order.status.replace("_", " ") }}
              </span>
              <span class="text-muted-foreground">{{ order.create_date.slice(0, 10) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
