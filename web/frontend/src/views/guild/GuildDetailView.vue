<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";
import ApplicationsTab from "./tabs/ApplicationsTab.vue";
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
const auth = useAuthStore();
const guild = useGuildStore();
const guildId = route.params.id as string;

const activeSection = ref("language");
const switcherOpen = ref(false);

const otherManagedGuilds = computed(() =>
  auth.guilds.filter((g) => g.bot_present && g.id !== guildId),
);

function switchGuild(id: string) {
  const g = auth.guildById(id);
  if (g) guild.setCurrent(g);
  switcherOpen.value = false;
  router.push(`/guilds/${id}`);
}


const sectionGroups = [
  {
    label: "General",
    items: [
      { id: "language", label: "Language", icon: "mdi:translate", component: LanguageTab },
      { id: "reminders", label: "Reminders", icon: "mdi:bell-outline", component: RemindersTab },
    ],
  },
  {
    label: "Moderation",
    items: [
      { id: "moderator-roles", label: "Moderator Roles", icon: "mdi:shield-account", component: ModeratorRolesTab },
      { id: "auto-kicker", label: "Auto-Kicker", icon: "mdi:account-remove", component: AutoKickerTab },
      { id: "auto-delete", label: "Auto-Delete", icon: "mdi:delete-clock", component: AutoDeleteTab },
      { id: "leave-messages", label: "Leave Messages", icon: "mdi:door-open", component: LeaveMessagesTab },
    ],
  },
  {
    label: "Roles",
    items: [
      { id: "role-mappings", label: "Role Mappings", icon: "mdi:account-switch", component: RoleMappingsTab },
      { id: "reaction-roles", label: "Reaction Roles", icon: "mdi:emoticon-outline", component: ReactionRolesTab },
    ],
  },
  {
    label: "Community",
    items: [
      { id: "applications", label: "Applications", icon: "mdi:file-document-outline", component: ApplicationsTab },
    ],
  },
  {
    label: "WoW",
    items: [
      { id: "wow", label: "WoW", icon: "mdi:sword-cross", component: WowTab },
    ],
  },
];

const allSections = sectionGroups.flatMap((g) => g.items);

const activeComponent = computed(() => allSections.find((s) => s.id === activeSection.value)?.component);

function guildIconUrl(): string | null {
  const g = guild.current;
  if (!g?.icon) return null;
  return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
}
</script>

<template>
  <!-- Click-outside overlay to close guild switcher -->
  <div
    v-if="switcherOpen"
    class="fixed inset-0 z-10"
    @click="switcherOpen = false"
  />

  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-56 flex-shrink-0 border-r border-border flex flex-col overflow-y-auto">
      <!-- Guild switcher -->
      <div class="relative border-b border-border">
        <button
          class="w-full p-4 flex items-center gap-2.5 hover:bg-muted transition-colors text-left"
          @click="switcherOpen = !switcherOpen"
        >
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
          <span class="font-semibold text-sm truncate flex-1">{{ guild.current?.name ?? "Guild" }}</span>
          <Icon
            :icon="switcherOpen ? 'mdi:chevron-up' : 'mdi:chevron-down'"
            class="w-4 h-4 text-muted-foreground flex-shrink-0"
          />
        </button>

        <!-- Dropdown -->
        <div
          v-if="switcherOpen"
          class="absolute left-0 right-0 top-full z-20 bg-card border border-border rounded-b-md shadow-lg overflow-hidden"
        >
          <button
            v-for="g in otherManagedGuilds"
            :key="g.id"
            class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm hover:bg-muted transition-colors text-left"
            @click="switchGuild(g.id)"
          >
            <img
              v-if="g.icon"
              :src="`https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`"
              :alt="g.name"
              class="w-6 h-6 rounded-full object-cover flex-shrink-0"
            />
            <div
              v-else
              class="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs font-bold flex-shrink-0"
              aria-hidden="true"
            >
              {{ g.name.charAt(0).toUpperCase() }}
            </div>
            <span class="truncate">{{ g.name }}</span>
          </button>
          <div v-if="otherManagedGuilds.length > 0" class="border-t border-border" />
          <button
            class="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-left"
            @click="router.push('/guilds'); switcherOpen = false"
          >
            <Icon icon="mdi:view-grid-outline" class="w-4 h-4 flex-shrink-0" />
            All Servers
          </button>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-2 space-y-4">
        <div v-for="group in sectionGroups" :key="group.label">
          <p class="px-3 pb-1 text-xs font-semibold text-muted-foreground/50 uppercase tracking-wider">
            {{ group.label }}
          </p>
          <div class="space-y-0.5">
            <button
              v-for="section in group.items"
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
          </div>
        </div>
      </nav>
    </aside>

    <!-- Content area -->
    <main class="flex-1 overflow-y-auto p-8">
      <component :is="activeComponent" :guild-id="guildId" />
    </main>
  </div>
</template>
