<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { BotGuildInfo } from "@/api/types";
import { useI18n } from "@/i18n";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const { t, locale } = useI18n();
const auth = useAuthStore();

const guilds = ref<BotGuildInfo[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

async function fetchGuilds() {
  if (loading.value) return;
  loading.value = true;
  error.value = null;
  try {
    const res = await api.get<{ guilds: BotGuildInfo[] }>("/operator/guilds");
    const managedIds = new Set(auth.guilds.map((g) => g.id));
    guilds.value = res.guilds.filter((g) => !managedIds.has(g.id));
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
}

function guildIconUrl(g: BotGuildInfo): string | null {
  if (!g.icon) return null;
  return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
}

function navigate(id: string) {
  router.push(`/guilds/${id}`);
}

onMounted(fetchGuilds);
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-1">
      <div class="flex items-center gap-2">
        <Icon icon="mdi:server-network-outline" class="w-5 h-5 text-teal-400" />
        <h2 class="text-xl font-bold">{{ t("tabs.operator_guilds.title") }}</h2>
      </div>
      <button
        class="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 flex items-center gap-1.5 hover:bg-primary/90 transition-colors"
        :disabled="loading"
        @click="fetchGuilds"
      >
        <Icon icon="mdi:refresh" class="w-4 h-4" :class="{ 'animate-spin': loading }" />
        {{ t("common.refresh") }}
      </button>
    </div>
    <p class="text-muted-foreground text-sm mb-6">{{ t("tabs.operator_guilds.desc") }}</p>

    <!-- Loading -->
    <div v-if="loading && guilds.length === 0" class="flex items-center gap-2 text-muted-foreground text-sm py-4">
      <Icon icon="mdi:loading" class="w-4 h-4 animate-spin" />
      {{ t("tabs.operator_guilds.loading") }}
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="flex items-center gap-2 bg-destructive/10 border border-destructive/30 rounded px-4 py-3 text-destructive text-sm"
    >
      <Icon icon="mdi:alert-circle-outline" class="w-5 h-5 flex-shrink-0" />
      {{ error }}
    </div>

    <!-- Empty -->
    <p v-else-if="guilds.length === 0" class="text-muted-foreground text-sm">
      {{ t("tabs.operator_guilds.empty") }}
    </p>

    <!-- Guild grid -->
    <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <button
        v-for="g in guilds"
        :key="g.id"
        class="flex items-center gap-3 bg-card border border-border rounded px-4 py-3 text-left hover:bg-muted hover:border-primary/40 transition-colors group"
        @click="navigate(g.id)"
      >
        <img
          v-if="guildIconUrl(g)"
          :src="guildIconUrl(g)!"
          :alt="g.name"
          class="w-9 h-9 rounded-full object-cover flex-shrink-0"
        />
        <div
          v-else
          class="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center flex-shrink-0"
          aria-hidden="true"
        >
          <span class="text-sm font-bold text-primary">{{ g.name.charAt(0).toUpperCase() }}</span>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium truncate group-hover:text-primary transition-colors">{{ g.name }}</p>
          <p class="text-xs text-muted-foreground">
            {{ g.member_count !== null ? t("tabs.operator_guilds.members", { count: g.member_count.toLocaleString(locale.current) }) : "—" }}
          </p>
        </div>
        <Icon icon="mdi:chevron-right" class="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
      </button>
    </div>

    <!-- Footer count -->
    <p v-if="guilds.length > 0" class="text-xs text-muted-foreground mt-4">
      {{ t(guilds.length === 1 ? "tabs.operator_guilds.count_one" : "tabs.operator_guilds.count_many", { count: guilds.length }) }}
    </p>
  </div>
</template>
