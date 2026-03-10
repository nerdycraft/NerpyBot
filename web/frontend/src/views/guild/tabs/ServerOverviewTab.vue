<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";
import type { GuildSummary } from "@/api/types";

const auth = useAuthStore();
const guildStore = useGuildStore();
const router = useRouter();

const managedGuilds = computed(() => auth.guilds.filter((g) => g.bot_present));
const invitableGuilds = computed(() => auth.guilds.filter((g) => !g.bot_present));

function iconUrl(guild: GuildSummary): string | null {
  if (!guild.icon) return null;
  return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`;
}
</script>

<template>
  <div>
    <h2 class="text-xl font-bold mb-1">Your Servers</h2>
    <p class="text-muted-foreground text-sm mb-6">All servers where NerpyBot is active and you have access to the dashboard. Click any card to jump to that server's settings — the currently selected server is highlighted with a "Current" badge.</p>

    <div v-if="managedGuilds.length === 0" class="text-muted-foreground text-sm mb-8">
      NerpyBot is not in any of your servers yet.
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-10">
      <button
        v-for="guild in managedGuilds"
        :key="guild.id"
        :disabled="guild.id === guildStore.current?.id"
        :class="[
          'rounded-lg p-4 flex items-center gap-3 text-left border transition-colors',
          guild.id === guildStore.current?.id
            ? 'bg-primary/5 border-primary cursor-default'
            : 'bg-card hover:bg-muted border-border hover:border-primary',
        ]"
        @click="router.push(`/guilds/${guild.id}`)"
      >
        <img
          v-if="iconUrl(guild)"
          :src="iconUrl(guild)!"
          :alt="guild.name"
          class="w-10 h-10 rounded-full object-cover flex-shrink-0"
        />
        <div
          v-else
          class="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-base font-bold flex-shrink-0"
          aria-hidden="true"
        >
          {{ guild.name.charAt(0).toUpperCase() }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="font-semibold text-sm truncate">{{ guild.name }}</div>
          <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
        </div>
        <span
          v-if="guild.id === guildStore.current?.id"
          class="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/15 text-primary flex-shrink-0"
        >
          Current
        </span>
        <Icon v-else icon="mdi:arrow-right" class="w-4 h-4 text-muted-foreground flex-shrink-0" />
      </button>
    </div>

    <template v-if="invitableGuilds.length > 0">
      <h3 class="text-base font-semibold mb-1">Add to a Server</h3>
      <p class="text-muted-foreground text-sm mb-4">
        You have sufficient permissions to invite NerpyBot to these servers.
      </p>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="guild in invitableGuilds"
          :key="guild.id"
          class="bg-card rounded-lg p-4 flex items-center gap-3 border border-border opacity-75"
        >
          <img
            v-if="iconUrl(guild)"
            :src="iconUrl(guild)!"
            :alt="guild.name"
            class="w-10 h-10 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-base font-bold flex-shrink-0"
            aria-hidden="true"
          >
            {{ guild.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="font-semibold text-sm truncate">{{ guild.name }}</div>
            <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
          </div>
          <a
            v-if="guild.invite_url"
            :href="guild.invite_url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-xs font-medium px-2.5 py-1 rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity whitespace-nowrap"
            @click.stop
          >
            Invite
          </a>
        </div>
      </div>
    </template>
  </div>
</template>
