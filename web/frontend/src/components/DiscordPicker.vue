<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed, ref, watch } from "vue";
import { api } from "@/api/client";
import type { DiscordChannel, DiscordRole } from "@/api/types";

const props = defineProps<{
  modelValue: string;
  guildId: string;
  kind: "channel" | "role";
  placeholder?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  "update:modelName": [name: string];
}>();

type Item = { id: string; name: string };

const items = ref<Item[]>([]);
const loading = ref(true);
const open = ref(false);
const query = ref("");
const inputEl = ref<HTMLInputElement | null>(null);

// Discord text channel types: 0=text, 5=announcement
const TEXT_CHANNEL_TYPES = new Set([0, 5]);

let _loadSeq = 0;

async function loadItems() {
  const seq = ++_loadSeq;
  loading.value = true;
  items.value = [];
  try {
    if (props.kind === "channel") {
      const data = await api.get<{ channels: DiscordChannel[] }>(`/guilds/${props.guildId}/discord/channels`);
      if (seq !== _loadSeq) return;
      items.value = data.channels
        .filter((c) => TEXT_CHANNEL_TYPES.has(c.type))
        .map((c) => ({ id: c.id, name: c.name }));
    } else {
      const data = await api.get<{ roles: DiscordRole[] }>(`/guilds/${props.guildId}/discord/roles`);
      if (seq !== _loadSeq) return;
      items.value = data.roles.map((r) => ({ id: r.id, name: r.name }));
    }
  } catch {
    // bot offline or error — fall back to plain text input
  } finally {
    if (seq === _loadSeq) loading.value = false;
  }
}

watch(() => [props.guildId, props.kind] as const, loadItems, { immediate: true });

const selectedName = computed(() => items.value.find((i) => i.id === props.modelValue)?.name ?? props.modelValue ?? "");

const filtered = computed(() => {
  const q = query.value.toLowerCase();
  if (!q) return items.value;
  return items.value.filter((i) => i.name.toLowerCase().includes(q));
});

const defaultPlaceholder = computed(() => (props.kind === "channel" ? "Select channel…" : "Select role…"));

function onFocus() {
  query.value = "";
  open.value = true;
}

function onContainerFocusOut(e: FocusEvent) {
  const wrapper = e.currentTarget as Element;
  const related = e.relatedTarget as Element | null;
  if (related && wrapper.contains(related)) return;
  open.value = false;
  query.value = "";
}

function select(item: Item) {
  emit("update:modelValue", item.id);
  emit("update:modelName", item.name);
  open.value = false;
  query.value = "";
  inputEl.value?.blur();
}

// Allow manually typing a raw ID when bot is offline
function onInputManual(e: Event) {
  const val = (e.target as HTMLInputElement).value;
  query.value = val;
  if (items.value.length === 0) {
    emit("update:modelValue", val);
    emit("update:modelName", "");
  } else {
    open.value = true;
  }
}
</script>

<template>
  <div class="relative" @focusout="onContainerFocusOut">
    <div class="relative">
      <Icon
        :icon="kind === 'channel' ? 'mdi:pound' : 'mdi:at'"
        class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none"
      />
      <input
        ref="inputEl"
        :value="open ? query : selectedName"
        :placeholder="loading ? 'Loading…' : (placeholder ?? defaultPlaceholder)"
        :disabled="loading"
        class="bg-input border border-border rounded pl-7 pr-3 py-2 text-sm w-full disabled:opacity-50"
        @focus="onFocus"
        @input="onInputManual"
        @keydown.escape="open = false"
      />
    </div>

    <!-- Dropdown -->
    <div
      v-if="open && filtered.length > 0"
      data-dropdown
      class="absolute left-0 right-0 top-full mt-1 z-30 bg-card border border-border rounded-md shadow-lg max-h-48 overflow-y-auto scrollbar-thin"
    >
      <button
        v-for="item in filtered"
        :key="item.id"
        class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-muted transition-colors"
        :class="{ 'bg-primary/10 text-primary': item.id === modelValue }"
        @mousedown.prevent="select(item)"
      >
        <Icon
          :icon="kind === 'channel' ? 'mdi:pound' : 'mdi:circle-small'"
          class="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground"
        />
        <span class="truncate">{{ item.name }}</span>
      </button>
    </div>

    <p v-if="open && !loading && items.length === 0" class="mt-1 text-xs text-muted-foreground">
      Bot offline — enter ID manually
    </p>
  </div>
</template>
