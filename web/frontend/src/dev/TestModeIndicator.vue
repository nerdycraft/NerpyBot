<script setup lang="ts">
import { Icon } from "@iconify/vue";
// This component is only imported when VITE_TEST_MODE === "true" (via defineAsyncComponent guard),
// so we always render — no conditional needed.
</script>

<template>
  <div
    class="flex items-center gap-1.5 text-amber-400 text-xs font-medium px-2 py-1 rounded bg-amber-400/10 border border-amber-400/20"
    title="Test mode active — using synthetic data"
  >
    <Icon icon="mdi:flask-outline" class="w-3.5 h-3.5 flex-shrink-0" />
    <span>Test Mode</span>
  </div>
</template>
