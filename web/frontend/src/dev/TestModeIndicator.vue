<script setup lang="ts">
import { Icon } from "@iconify/vue";
// This component is only imported when VITE_TEST_MODE === "true" (via defineAsyncComponent guard),
// so we always render — no conditional needed.
</script>

<template>
  <div
    class="w-full flex items-center gap-2 px-4 py-2 bg-amber-400/10 border-t border-amber-400/25 text-amber-400 text-xs font-medium"
    title="Test mode active — using synthetic data"
  >
    <Icon icon="mdi:flask-outline" class="w-3.5 h-3.5 flex-shrink-0" />
    <span class="truncate">Test mode — synthetic data</span>
  </div>
</template>
