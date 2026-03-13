<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useAuthStore } from "@/stores/auth";
import { useGuildStore } from "@/stores/guild";
import ServerOverviewTab from "./tabs/ServerOverviewTab.vue";
import ApplicationFormsTab from "./tabs/ApplicationFormsTab.vue";
import ApplicationTemplatesTab from "./tabs/ApplicationTemplatesTab.vue";
import ApplicationSubmissionsTab from "./tabs/ApplicationSubmissionsTab.vue";
import LanguageTab from "./tabs/LanguageTab.vue";
import ModeratorRolesTab from "./tabs/ModeratorRolesTab.vue";
import LeaveMessagesTab from "./tabs/LeaveMessagesTab.vue";
import AutoDeleteTab from "./tabs/AutoDeleteTab.vue";
import AutoKickerTab from "./tabs/AutoKickerTab.vue";
import RoleMappingsTab from "./tabs/RoleMappingsTab.vue";
import RemindersTab from "./tabs/RemindersTab.vue";
import ReactionRolesTab from "./tabs/ReactionRolesTab.vue";
import WowGuildNewsTab from "./tabs/WowGuildNewsTab.vue";
import WowCraftingTab from "./tabs/WowCraftingTab.vue";
import OperatorUserManagementTab from "./tabs/OperatorUserManagementTab.vue";
import OperatorDashboardTab from "./tabs/OperatorDashboardTab.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const guild = useGuildStore();

// Reactive — Vue Router reuses the component instance when navigating between guilds.
const guildId = computed(() => route.params.id as string | undefined);

const activeSection = computed(() => (route.query.tab as string) ?? "server-overview");
const switcherOpen = ref(false);
const sidebarOpen = ref(true);
const LG_BREAKPOINT = 1024;

onMounted(() => {
  if (window.innerWidth < LG_BREAKPOINT) sidebarOpen.value = false;
});

// Reset to overview when switching guilds
watch(guildId, () => {
  router.replace({ query: {} });
});

const otherManagedGuilds = computed(() =>
  auth.guilds.filter((g) => g.bot_present && g.id !== guildId.value),
);

function switchGuild(id: string) {
  const g = auth.guildById(id);
  if (g) guild.setCurrent(g);
  switcherOpen.value = false;
  router.push(`/guilds/${id}`);
  if (window.innerWidth < LG_BREAKPOINT) sidebarOpen.value = false;
}

function navigateTo(tabId: string) {
  router.replace({ query: { tab: tabId } });
  if (window.innerWidth < LG_BREAKPOINT) sidebarOpen.value = false;
}

type SectionItem = {
  id: string;
  label: string;
  icon: string;
  component: unknown;
  guildOnly?: boolean;
};

type SectionGroup = {
  label: string;
  operatorOnly?: boolean;
  items: SectionItem[];
};

const allSectionGroups: SectionGroup[] = [
  {
    label: "General",
    items: [
      { id: "server-overview", label: "Server Overview", icon: "mdi:view-grid-outline", component: ServerOverviewTab },
      { id: "language", label: "Language", icon: "mdi:translate", component: LanguageTab, guildOnly: true },
      { id: "reminders", label: "Reminders", icon: "mdi:bell-outline", component: RemindersTab, guildOnly: true },
    ],
  },
  {
    label: "Moderation",
    items: [
      { id: "moderator-roles", label: "Moderator Roles", icon: "mdi:shield-account", component: ModeratorRolesTab, guildOnly: true },
      { id: "auto-kicker", label: "Auto-Kicker", icon: "mdi:account-remove", component: AutoKickerTab, guildOnly: true },
      { id: "auto-delete", label: "Auto-Delete", icon: "mdi:delete-clock", component: AutoDeleteTab, guildOnly: true },
      { id: "leave-messages", label: "Leave Messages", icon: "mdi:door-open", component: LeaveMessagesTab, guildOnly: true },
    ],
  },
  {
    label: "Roles",
    items: [
      { id: "role-mappings", label: "Role Mappings", icon: "mdi:account-switch", component: RoleMappingsTab, guildOnly: true },
      { id: "reaction-roles", label: "Reaction Roles", icon: "mdi:emoticon-outline", component: ReactionRolesTab, guildOnly: true },
    ],
  },
  {
    label: "Applications",
    items: [
      { id: "application-forms", label: "Forms", icon: "mdi:file-document-outline", component: ApplicationFormsTab, guildOnly: true },
      { id: "application-templates", label: "Templates", icon: "mdi:file-document-multiple-outline", component: ApplicationTemplatesTab, guildOnly: true },
      { id: "application-submissions", label: "Submissions", icon: "mdi:file-account-outline", component: ApplicationSubmissionsTab, guildOnly: true },
    ],
  },
  {
    label: "WoW",
    items: [
      { id: "wow-guild-news", label: "Guild News", icon: "mdi:newspaper-variant-outline", component: WowGuildNewsTab, guildOnly: true },
      { id: "wow-crafting", label: "Crafting Boards", icon: "mdi:hammer-wrench", component: WowCraftingTab, guildOnly: true },
    ],
  },
  {
    label: "Operator",
    operatorOnly: true,
    items: [
      { id: "operator-dashboard", label: "Bot Health", icon: "mdi:heart-pulse", component: OperatorDashboardTab },
      { id: "operator-user-management", label: "User Management", icon: "mdi:crown-outline", component: OperatorUserManagementTab },
    ],
  },
];

const sectionGroups = computed(() =>
  allSectionGroups
    .map((g) => ({ ...g, items: g.items.filter((item) => !item.guildOnly || !!guildId.value) }))
    .filter((g) => g.items.length > 0)
    .filter((g) => !g.operatorOnly || auth.user?.is_operator),
);

const allSections = computed(() => sectionGroups.value.flatMap((g) => g.items));
const activeComponent = computed(() => {
  const found = allSections.value.find((s) => s.id === activeSection.value);
  if (!found && allSections.value.length > 0) {
    // Requested tab is no longer available (filtered out) — fall back silently.
    router.replace({ query: { tab: allSections.value[0]!.id } });
    return allSections.value[0]!.component;
  }
  return found?.component;
});

// Support mode: operator browsing a guild they don't personally manage
const supportMode = computed(() =>
  !!auth.user?.is_operator &&
  !!guildId.value &&
  !auth.guildById(guildId.value)
);

const GROUP_ACCENTS: Record<string, string> = {
  General:      "text-blue-400",
  Moderation:   "text-amber-400",
  Roles:        "text-violet-400",
  Applications: "text-emerald-400",
  WoW:          "text-yellow-400",
  Operator:     "text-rose-400",
};

function guildIconUrl(): string | null {
  const g = guild.current;
  if (!g?.icon) return null;
  return `https://cdn.discordapp.com/icons/${g.id}/${g.icon}.png`;
}
</script>

<template>
  <!-- Click-outside overlay to close guild switcher -->
  <div v-if="switcherOpen" class="fixed inset-0 z-10" @click="switcherOpen = false" />

  <div class="flex flex-col h-screen overflow-hidden">
    <!-- Mobile top bar — only visible below lg breakpoint -->
    <div class="lg:hidden flex items-center h-12 px-4 border-b border-border flex-shrink-0 bg-card gap-3">
      <button
        class="text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Open navigation"
        @click="sidebarOpen = true"
      >
        <Icon icon="mdi:menu" class="w-5 h-5" />
      </button>
      <span class="font-semibold text-sm truncate">
        {{ guildId ? (guild.current?.name ?? "Guild") : "NerpyBot" }}
      </span>
    </div>

    <!-- Row: sidebar + content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Mobile backdrop — closes sidebar when tapped -->
      <Transition
        enter-active-class="transition-opacity duration-200"
        leave-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="sidebarOpen"
          class="fixed inset-0 bg-black/40 z-20 lg:hidden"
          aria-hidden="true"
          @click="sidebarOpen = false"
        />
      </Transition>
      <!-- Sidebar -->
      <aside
      :class="[
        'flex flex-col border-r border-border bg-card flex-shrink-0',
        'fixed lg:relative inset-y-0 left-0 z-30',
        'overflow-hidden transition-[width,transform] duration-200 ease-in-out',
        sidebarOpen
          ? 'w-56 translate-x-0'
          : 'w-0 -translate-x-full lg:w-12 lg:translate-x-0',
      ]"
    >
      <!-- Rainbow accent bar -->
      <div class="h-0.5 bg-gradient-to-r from-blue-500 via-violet-500 via-fuchsia-500 to-teal-400 flex-shrink-0" />
      <!-- Collapse toggle (desktop only) -->
      <div class="hidden lg:flex justify-end px-2 py-1 flex-shrink-0">
        <button
          class="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          :title="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
          :aria-label="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
          @click="sidebarOpen = !sidebarOpen"
        >
          <Icon
            :icon="sidebarOpen ? 'mdi:chevron-left' : 'mdi:chevron-right'"
            class="w-4 h-4"
          />
        </button>
      </div>
      <!-- Guild switcher -->
      <div class="relative border-b border-border flex-shrink-0">
        <button
          class="w-full p-4 flex items-center gap-2.5 hover:bg-muted transition-colors text-left"
          @click="guildId ? (switcherOpen = !switcherOpen) : undefined"
          :class="{ 'cursor-default': !guildId }"
        >
          <img
            v-if="guildId && guildIconUrl()"
            :src="guildIconUrl()!"
            :alt="guild.current?.name"
            class="w-8 h-8 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0"
            aria-hidden="true"
          >
            <Icon v-if="!guildId" icon="mdi:robot-outline" class="w-4 h-4 text-primary" />
            <span v-else class="text-xs font-bold text-primary">
              {{ guild.current?.name?.charAt(0).toUpperCase() ?? "?" }}
            </span>
          </div>
          <span v-show="sidebarOpen" class="font-semibold text-sm truncate flex-1">
            {{ guildId ? (guild.current?.name ?? "Guild") : "NerpyBot" }}
          </span>
          <Icon
            v-if="guildId"
            v-show="sidebarOpen"
            :icon="switcherOpen ? 'mdi:chevron-up' : 'mdi:chevron-down'"
            class="w-4 h-4 text-muted-foreground flex-shrink-0"
          />
        </button>

        <!-- Dropdown (only when a guild is selected) -->
        <div
          v-if="switcherOpen && guildId"
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
      <nav class="flex-1 p-2 space-y-4 overflow-y-auto">
        <div v-for="group in sectionGroups" :key="group.label">
          <p v-show="sidebarOpen" :class="['px-3 pb-1 text-xs font-semibold uppercase tracking-wider', GROUP_ACCENTS[group.label] ?? 'text-muted-foreground/50']">
            {{ group.label }}
          </p>
          <div class="space-y-0.5">
            <button
              v-for="section in group.items"
              :key="section.id"
              :class="[
                'w-full flex items-center py-2 rounded-md text-sm transition-colors text-left',
                sidebarOpen ? 'gap-2.5' : 'justify-center',
                activeSection === section.id
                  ? 'bg-primary/15 text-primary font-medium border-l-2 border-primary pl-[10px]'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted border-l-2 border-transparent pl-[10px]',
                !sidebarOpen && 'lg:border-l-0 lg:px-0',
              ]"
              :title="!sidebarOpen ? section.label : undefined"
              :aria-label="section.label"
              @click="navigateTo(section.id)"
            >
              <Icon :icon="section.icon" class="w-4 h-4 flex-shrink-0" />
              <span v-show="sidebarOpen">{{ section.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Sidebar footer -->
      <div class="border-t border-border p-4 flex items-center gap-3 flex-shrink-0">
        <span v-show="sidebarOpen" class="text-sm text-muted-foreground truncate flex-1">
          {{ auth.user?.username }}
        </span>
        <button
          :class="[
            'p-2 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors flex-shrink-0',
            !sidebarOpen && 'mx-auto',
          ]"
          title="Logout"
          aria-label="Logout"
          @click="auth.clear(); router.push('/login')"
        >
          <Icon icon="mdi:logout" class="w-5 h-5" />
        </button>
      </div>
      </aside>

      <!-- Content area -->
      <main class="flex-1 overflow-y-auto p-8">
        <!-- Support mode banner -->
        <div
          v-if="supportMode"
          class="mb-6 flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 rounded px-4 py-3 text-amber-400 text-sm"
        >
          <Icon icon="mdi:eye-outline" class="w-4 h-4 flex-shrink-0" />
          <span>
            <strong>Support Mode</strong> — Viewing as operator. Sensitive content is redacted. Write operations are disabled.
          </span>
        </div>
        <div class="max-w-4xl">
          <component :is="activeComponent" :guild-id="guildId" />
        </div>
      </main>
    </div>
  </div>
</template>
