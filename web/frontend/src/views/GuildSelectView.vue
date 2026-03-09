<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import type { GuildSummary } from "@/api/types";

const auth = useAuthStore();
const router = useRouter();

const managedGuilds = computed(() => auth.guilds.filter((g) => g.bot_present));
const invitableGuilds = computed(() => auth.guilds.filter((g) => !g.bot_present));

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

      <!-- Managed servers -->
      <h1 class="text-2xl font-bold mb-2">Your Servers</h1>
      <p class="text-muted-foreground mb-6">Select a server to manage its settings.</p>

      <div v-if="managedGuilds.length === 0" class="text-muted-foreground mb-8">
        NerpyBot is not in any of your servers yet.
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
        <button
          v-for="guild in managedGuilds"
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

      <!-- Invitable servers -->
      <template v-if="invitableGuilds.length > 0">
        <h2 class="text-lg font-semibold mb-2">Add to a Server</h2>
        <p class="text-muted-foreground mb-6">
          You have sufficient permissions to invite NerpyBot to these servers.
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="guild in invitableGuilds"
            :key="guild.id"
            class="bg-card rounded-lg p-5 flex items-center gap-4 border border-border opacity-75"
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
            <div class="min-w-0 flex-1">
              <div class="font-semibold truncate">{{ guild.name }}</div>
              <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
            </div>
            <a
              v-if="guild.invite_url"
              :href="guild.invite_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-xs font-medium px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity whitespace-nowrap"
            >
              Invite Bot
            </a>
          </div>
        </div>
      </template>

    </div>
  </div>
</template>
