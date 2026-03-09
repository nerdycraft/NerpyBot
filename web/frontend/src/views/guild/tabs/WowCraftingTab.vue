<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { CraftingBoardSchema, CraftingOrderSchema } from "@/api/types";
import { useGuildEntities } from "@/composables/useGuildEntities";

const props = defineProps<{ guildId: string }>();

const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const boards = ref<CraftingBoardSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const orders = ref<CraftingOrderSchema[]>([]);
const ordersLoading = ref(false);
const ordersError = ref<string | null>(null);
const statusFilter = ref<string>("");

const STATUS_LABELS: Record<string, string> = {
  "": "All",
  open: "Open",
  completed: "Completed",
  cancelled: "Cancelled",
};

const STATUS_COLORS: Record<string, string> = {
  open: "text-yellow-400",
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

onMounted(async () => {
  void fetchChannels();
  try {
    const config = await api.get<{ crafting_boards: CraftingBoardSchema[] }>(`/guilds/${props.guildId}/wow`);
    boards.value = config.crafting_boards;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
  await fetchOrders();
});

watch(statusFilter, fetchOrders);
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Crafting Boards</h2>
      <p class="text-muted-foreground text-sm">Crafting boards and active orders (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else class="space-y-8">
      <!-- Boards -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">Boards</h3>
        <p v-if="boards.length === 0" class="text-muted-foreground text-sm">No crafting boards configured.</p>
        <div
          v-for="cb in boards"
          :key="cb.id"
          class="bg-card border border-border rounded px-4 py-3"
        >
          <div class="text-sm text-muted-foreground">#{{ channelName(cb.channel_id) }}</div>
          <div v-if="cb.description" class="text-xs mt-1">{{ cb.description }}</div>
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
              <div v-if="order.notes" class="text-xs text-muted-foreground truncate">{{ order.notes }}</div>
            </div>

            <div class="flex items-center gap-3 text-xs flex-shrink-0">
              <span :class="STATUS_COLORS[order.status] ?? 'text-muted-foreground'" class="capitalize font-medium">
                {{ order.status }}
              </span>
              <span class="text-muted-foreground">{{ order.create_date.slice(0, 10) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
