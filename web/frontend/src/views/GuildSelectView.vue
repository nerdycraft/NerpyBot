<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import type { GuildSummary } from "@/api/types";

const auth = useAuthStore();
const router = useRouter();

const guilds = computed(() => auth.guilds);

function select(guildId: string) {
  router.push(`/guilds/${guildId}`);
}

function iconUrl(guild: GuildSummary): string | null {
  if (!guild.icon) return null;
  return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`;
}
</script>

<template>
  <div class="min-h-screen p-8">
    <div class="max-w-5xl mx-auto">
      <h1 class="text-2xl font-bold mb-2">Your Servers</h1>
      <p class="text-muted-foreground mb-8">Select a server to manage its settings.</p>

      <div v-if="guilds.length === 0" class="text-muted-foreground">
        No servers found. Make sure you have admin or moderator permissions in at least one server where NerpyBot is present.
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <button
          v-for="guild in guilds"
          :key="guild.id"
          class="bg-card hover:bg-muted rounded-lg p-5 flex items-center gap-4 text-left transition-colors border border-border hover:border-primary"
          @click="select(guild.id)"
        >
          <img
            v-if="iconUrl(guild)"
            :src="iconUrl(guild)!"
            :alt="guild.name"
            class="w-12 h-12 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-lg font-bold flex-shrink-0"
            aria-hidden="true"
          >
            {{ guild.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0">
            <div class="font-semibold truncate">{{ guild.name }}</div>
            <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>
