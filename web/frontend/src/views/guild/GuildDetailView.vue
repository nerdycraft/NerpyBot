<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useGuildStore } from "@/stores/guild";
import { api } from "@/api/client";
import type { ReminderSchema, ReactionRoleMessageSchema } from "@/api/types";
import LanguageTab from "./tabs/LanguageTab.vue";
import ModeratorRolesTab from "./tabs/ModeratorRolesTab.vue";
import LeaveMessagesTab from "./tabs/LeaveMessagesTab.vue";
import AutoDeleteTab from "./tabs/AutoDeleteTab.vue";
import AutoKickerTab from "./tabs/AutoKickerTab.vue";
import RoleMappingsTab from "./tabs/RoleMappingsTab.vue";
import RemindersTab from "./tabs/RemindersTab.vue";
import ReactionRolesTab from "./tabs/ReactionRolesTab.vue";
import WowTab from "./tabs/WowTab.vue";

const route = useRoute();
const router = useRouter();
const guild = useGuildStore();
const guildId = route.params.id as string;

const activeSection = ref("language");

// Counts for conditional read-only sections — null means still loading
const remindersCount = ref<number | null>(null);
const reactionRolesCount = ref<number | null>(null);
const wowHasData = ref<boolean | null>(null);

interface WowConfig {
  guild_news: unknown[];
  crafting_boards: unknown[];
}

onMounted(async () => {
  const [reminders, reactionRoles, wow] = await Promise.allSettled([
    api.get<ReminderSchema[]>(`/guilds/${guildId}/reminders`),
    api.get<ReactionRoleMessageSchema[]>(`/guilds/${guildId}/reaction-roles`),
    api.get<WowConfig>(`/guilds/${guildId}/wow`),
  ]);
  remindersCount.value = reminders.status === "fulfilled" ? reminders.value.length : 0;
  reactionRolesCount.value = reactionRoles.status === "fulfilled" ? reactionRoles.value.length : 0;
  wowHasData.value =
    wow.status === "fulfilled" &&
    (wow.value.guild_news.length > 0 || wow.value.crafting_boards.length > 0);
});

const sections = [
  { id: "language", label: "Language", icon: "mdi:translate", component: LanguageTab, always: true },
  { id: "moderator-roles", label: "Moderator Roles", icon: "mdi:shield-account", component: ModeratorRolesTab, always: true },
  { id: "leave-messages", label: "Leave Messages", icon: "mdi:door-open", component: LeaveMessagesTab, always: true },
  { id: "auto-delete", label: "Auto-Delete", icon: "mdi:delete-clock", component: AutoDeleteTab, always: true },
  { id: "auto-kicker", label: "Auto-Kicker", icon: "mdi:account-remove", component: AutoKickerTab, always: true },
  { id: "role-mappings", label: "Role Mappings", icon: "mdi:account-switch", component: RoleMappingsTab, always: true },
  { id: "reminders", label: "Reminders", icon: "mdi:bell-outline", component: RemindersTab, always: false },
  { id: "reaction-roles", label: "Reaction Roles", icon: "mdi:emoticon-outline", component: ReactionRolesTab, always: false },
  { id: "wow", label: "WoW", icon: "mdi:sword-cross", component: WowTab, always: false },
];

const visibleSections = computed(() =>
  sections.filter((s) => {
    if (s.always) return true;
    if (s.id === "reminders") return (remindersCount.value ?? 0) > 0;
    if (s.id === "reaction-roles") return (reactionRolesCount.value ?? 0) > 0;
    if (s.id === "wow") return wowHasData.value === true;
    return false;
  }),
);

const activeComponent = computed(() => sections.find((s) => s.id === activeSection.value)?.component);

function guildIconUrl(): string | null {
  const g = guild.current;
  if (!g?.icon) return null;
  return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
}
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-56 flex-shrink-0 border-r border-border flex flex-col overflow-y-auto">
      <!-- Guild header + back link -->
      <div class="p-4 border-b border-border space-y-3">
        <button
          class="text-muted-foreground hover:text-foreground transition-colors text-sm flex items-center gap-1.5"
          @click="router.push('/guilds')"
        >
          <Icon icon="mdi:arrow-left" class="w-4 h-4" />
          All Servers
        </button>
        <div class="flex items-center gap-2.5">
          <img
            v-if="guildIconUrl()"
            :src="guildIconUrl()!"
            :alt="guild.current?.name"
            class="w-8 h-8 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-bold flex-shrink-0"
            aria-hidden="true"
          >
            {{ guild.current?.name?.charAt(0).toUpperCase() ?? "?" }}
          </div>
          <span class="font-semibold text-sm truncate">{{ guild.current?.name ?? "Guild" }}</span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-2 space-y-0.5">
        <button
          v-for="section in visibleSections"
          :key="section.id"
          :class="[
            'w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors text-left',
            activeSection === section.id
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted',
          ]"
          @click="activeSection = section.id"
        >
          <Icon :icon="section.icon" class="w-4 h-4 flex-shrink-0" />
          {{ section.label }}
        </button>
      </nav>
    </aside>

    <!-- Content area -->
    <main class="flex-1 overflow-y-auto p-8">
      <component :is="activeComponent" :guild-id="guildId" />
    </main>
  </div>
</template>
