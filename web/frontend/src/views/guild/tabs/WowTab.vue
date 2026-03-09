<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { WowGuildNewsSchema, CraftingBoardSchema } from "@/api/types";

interface WowConfig {
  guild_news: WowGuildNewsSchema[];
  crafting_boards: CraftingBoardSchema[];
}

const props = defineProps<{ guildId: string }>();

const config = ref<WowConfig | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    config.value = await api.get<WowConfig>(`/guilds/${props.guildId}/wow`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">World of Warcraft</h2>
      <p class="text-muted-foreground text-sm">WoW integration configuration (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else-if="config" class="space-y-8">
      <!-- Guild News Trackers -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">Guild News Trackers</h3>
        <p v-if="config.guild_news.length === 0" class="text-muted-foreground text-sm">None configured.</p>
        <div
          v-for="gn in config.guild_news"
          :key="gn.id"
          class="bg-card border border-border rounded px-4 py-3 space-y-1"
        >
          <div class="flex items-center justify-between">
            <span class="font-medium text-sm">{{ gn.wow_guild_name }} — {{ gn.wow_realm_slug }}</span>
            <span :class="gn.enabled ? 'text-green-400' : 'text-muted-foreground'" class="text-xs">
              {{ gn.region.toUpperCase() }} · {{ gn.enabled ? "Active" : "Disabled" }}
            </span>
          </div>
          <div class="text-muted-foreground text-xs">Channel: {{ gn.channel_id }}</div>
        </div>
      </div>

      <!-- Crafting Boards -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold">Crafting Boards</h3>
        <p v-if="config.crafting_boards.length === 0" class="text-muted-foreground text-sm">None configured.</p>
        <div
          v-for="cb in config.crafting_boards"
          :key="cb.id"
          class="bg-card border border-border rounded px-4 py-3"
        >
          <div class="font-mono text-sm text-muted-foreground">Channel {{ cb.channel_id }}</div>
          <div v-if="cb.description" class="text-xs mt-1">{{ cb.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
