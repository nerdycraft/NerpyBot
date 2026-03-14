<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "@/i18n";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";

const auth = useAuthStore();
const guildStore = useGuildStore();
const router = useRouter();
const { t } = useI18n();

const managedGuilds = computed(() => auth.guilds.filter((g) => g.bot_present));
const invitableGuilds = computed(() => auth.guilds.filter((g) => !g.bot_present));

function iconUrl(guild: { id: string; icon: string | null }): string | null {
  if (!guild.icon) return null;
  return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`;
}
</script>

<template>
  <div>
    <h2 class="text-xl font-bold mb-1">{{ t("tabs.server_overview.title") }}</h2>
    <p class="text-muted-foreground text-sm mb-6">{{ t("tabs.server_overview.desc") }}</p>

    <div v-if="managedGuilds.length === 0" class="text-muted-foreground text-sm mb-8">
      {{ t("tabs.server_overview.empty") }}
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
          {{ t("tabs.server_overview.current") }}
        </span>
        <Icon v-else icon="mdi:arrow-right" class="w-4 h-4 text-muted-foreground flex-shrink-0" />
      </button>
    </div>

    <template v-if="invitableGuilds.length > 0">
      <h3 class="text-base font-semibold mb-1">{{ t("tabs.server_overview.add_title") }}</h3>
      <p class="text-muted-foreground text-sm mb-4">{{ t("tabs.server_overview.add_desc") }}</p>

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
            {{ t("tabs.server_overview.invite") }}
          </a>
        </div>
      </div>
    </template>
  </div>
</template>
