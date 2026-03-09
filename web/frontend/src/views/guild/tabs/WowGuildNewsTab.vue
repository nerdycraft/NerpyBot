<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { WowGuildNewsSchema } from "@/api/types";
import { useGuildEntities } from "@/composables/useGuildEntities";

const props = defineProps<{ guildId: string }>();

const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const trackers = ref<WowGuildNewsSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  void fetchChannels();
  try {
    const config = await api.get<{ guild_news: WowGuildNewsSchema[] }>(`/guilds/${props.guildId}/wow`);
    trackers.value = config.guild_news;
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
      <h2 class="text-lg font-semibold">Guild News</h2>
      <p class="text-muted-foreground text-sm">WoW guild news trackers (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="trackers.length === 0" class="text-muted-foreground text-sm">No guild news trackers configured.</p>

    <div v-else class="space-y-3">
      <div
        v-for="gn in trackers"
        :key="gn.id"
        class="bg-card border border-border rounded px-4 py-3 space-y-1"
      >
        <div class="flex items-center justify-between">
          <span class="font-medium text-sm">{{ gn.wow_guild_name }} — {{ gn.wow_realm_slug }}</span>
          <span :class="gn.enabled ? 'text-green-400' : 'text-muted-foreground'" class="text-xs">
            {{ gn.region.toUpperCase() }} · {{ gn.enabled ? "Active" : "Disabled" }}
          </span>
        </div>
        <div class="text-muted-foreground text-xs">Channel: #{{ channelName(gn.channel_id) }}</div>
      </div>
    </div>
  </div>
</template>
