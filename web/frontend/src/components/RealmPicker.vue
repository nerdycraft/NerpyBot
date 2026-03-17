<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { api } from "@/api/client";
import type { RealmResult } from "@/api/types";

const props = defineProps<{ modelValue: string; region: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const query = ref(props.modelValue);
const results = ref<RealmResult[]>([]);
const loading = ref(false);
const open = ref(false);
const offline = ref(false);
let debounceTimer: ReturnType<typeof setTimeout> | null = null;
let requestSeq = 0;

// Reset when region changes
watch(
  () => props.region,
  () => {
    requestSeq += 1;
    if (debounceTimer) clearTimeout(debounceTimer);
    results.value = [];
    query.value = "";
    open.value = false;
    offline.value = false;
    emit("update:modelValue", "");
  },
);

function onInput(e: Event) {
  const val = (e.target as HTMLInputElement).value;
  query.value = val;
  emit("update:modelValue", val);
  if (debounceTimer) clearTimeout(debounceTimer);
  if (val.length < 2) {
    results.value = [];
    open.value = false;
    return;
  }
  debounceTimer = setTimeout(() => fetchRealms(val), 300);
}

async function fetchRealms(q: string) {
  const seq = ++requestSeq;
  loading.value = true;
  try {
    const data = await api.get<RealmResult[]>(`/wow/realms?region=${props.region}&q=${encodeURIComponent(q)}`);
    if (seq !== requestSeq) return;
    results.value = data;
    offline.value = false;
    open.value = data.length > 0;
  } catch {
    if (seq !== requestSeq) return;
    offline.value = true;
    results.value = [];
    open.value = false;
  } finally {
    if (seq === requestSeq) loading.value = false;
  }
}

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer);
});

function closeDropdown() {
  setTimeout(() => (open.value = false), 150);
}

function select(realm: RealmResult) {
  query.value = realm.name;
  emit("update:modelValue", realm.slug);
  open.value = false;
  results.value = [];
}
</script>

<template>
  <div class="relative">
    <input
      :value="query"
      type="text"
      :placeholder="region ? 'Search realm…' : 'Select a region first'"
      :disabled="!region"
      class="bg-input border border-border rounded px-3 py-2 text-sm w-full disabled:opacity-50"
      @input="onInput"
      @blur="closeDropdown"
    />
    <p v-if="offline" class="mt-1 text-xs text-muted-foreground">
      Bot offline — enter realm slug manually (e.g. blackrock)
    </p>
    <div
      v-if="open && results.length"
      class="absolute left-0 right-0 top-full mt-1 z-30 bg-card border border-border rounded-md shadow-lg max-h-48 overflow-y-auto scrollbar-thin"
    >
      <button
        v-for="r in results"
        :key="r.slug"
        class="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
        @mousedown.prevent="select(r)"
      >
        {{ r.name }}
      </button>
    </div>
  </div>
</template>
