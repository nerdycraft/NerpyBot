<script setup lang="ts">
import { Icon } from "@iconify/vue";
defineProps<{ text: string }>();
</script>

<template>
  <span :title="text" class="cursor-help inline-flex">
    <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" />
  </span>
</template>
