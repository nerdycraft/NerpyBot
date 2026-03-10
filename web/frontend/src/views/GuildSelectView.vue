<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";
import { api } from "@/api/client";
import type { GuildSummary, UserInfo } from "@/api/types";

const auth = useAuthStore();
const guild = useGuildStore();
const router = useRouter();

const managedGuilds = computed(() => auth.guilds.filter((g) => g.bot_present));
const invitableGuilds = computed(() => auth.guilds.filter((g) => !g.bot_present));

// Always refresh guild data on mount — ensures bot_present and invite_url are current
// even when the user object was restored from localStorage with stale field values.
onMounted(async () => {
  try {
    const me = await api.get<UserInfo>("/auth/me");
    auth.setUser(me);
  } catch {
    // silently ignore — stale cached data is better than a broken page
  }
});

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
      <p class="text-muted-foreground mb-6">Select a server to manage its settings.</p>

      <div v-if="managedGuilds.length === 0" class="text-muted-foreground mb-8">
        NerpyBot is not in any of your servers yet.
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
        <button
          v-for="g in managedGuilds"
          :key="g.id"
          :disabled="g.id === guild.current?.id"
          :class="[
            'rounded-lg p-5 flex items-center gap-4 text-left border transition-colors',
            g.id === guild.current?.id
              ? 'bg-primary/5 border-primary cursor-default'
              : 'bg-card hover:bg-muted border-border hover:border-primary',
          ]"
          @click="select(g.id)"
        >
          <img
            v-if="iconUrl(g)"
            :src="iconUrl(g)!"
            :alt="g.name"
            class="w-12 h-12 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-lg font-bold flex-shrink-0"
            aria-hidden="true"
          >
            {{ g.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="font-semibold truncate">{{ g.name }}</div>
            <div class="text-xs text-muted-foreground capitalize">{{ g.permission_level }}</div>
          </div>
          <span
            v-if="g.id === guild.current?.id"
            class="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/15 text-primary flex-shrink-0"
          >
            Current
          </span>
        </button>
      </div>

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
