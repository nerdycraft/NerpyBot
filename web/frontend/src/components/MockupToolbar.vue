<script setup lang="ts">
import { useMockup, type MockupLevel } from "@/composables/useMockup";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const { mockupLevel, setMockupLevel, clearMockup } = useMockup();

const levels: { value: MockupLevel; label: string }[] = [
  { value: "admin", label: "Admin" },
  { value: "mod", label: "Moderator" },
  { value: "member", label: "Member" },
];

function onSelect(e: Event) {
  const val = (e.target as HTMLSelectElement).value as MockupLevel;
  if (val) {
    setMockupLevel(val);
  } else {
    clearMockup();
  }
}
</script>

<template>
  <div v-if="auth.user?.is_operator">
    <!-- Active mockup banner -->
    <div
      v-if="mockupLevel"
      class="mb-4 flex items-center justify-between gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded px-4 py-2.5 text-yellow-400 text-sm"
    >
      <span>
        <strong>Mockup Mode</strong> — Simulating view as
        <strong>{{ mockupLevel }}</strong>. Some sections may be hidden.
      </span>
      <button
        class="text-xs underline hover:no-underline flex-shrink-0"
        @click="clearMockup"
      >
        Exit mockup
      </button>
    </div>

    <!-- Inactive — subtle dropdown -->
    <div v-else class="mb-4 flex items-center gap-2 text-xs text-muted-foreground/60">
      <span>Simulate view as:</span>
      <select
        class="bg-transparent border border-border rounded px-2 py-0.5 text-xs text-muted-foreground cursor-pointer hover:border-primary transition-colors"
        @change="onSelect"
      >
        <option value="">— choose level —</option>
        <option v-for="l in levels" :key="l.value!" :value="l.value!">{{ l.label }}</option>
      </select>
    </div>
  </div>
</template>
