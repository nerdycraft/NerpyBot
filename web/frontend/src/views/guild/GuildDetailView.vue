<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
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
import OperatorModulesTab from "./tabs/OperatorModulesTab.vue";
import OperatorGuildsTab from "./tabs/OperatorGuildsTab.vue";
import SupportTab from "./tabs/SupportTab.vue";
import MockupToolbar from "@/components/MockupToolbar.vue";
import LanguageSwitcher from "@/components/LanguageSwitcher.vue";
import { api } from "@/api/client";
import type { BotGuildInfo } from "@/api/types";
import { defineAsyncComponent } from "vue";

const TestModeIndicator =
  import.meta.env.VITE_TEST_MODE === "true"
    ? defineAsyncComponent(() => import("@/dev/TestModeIndicator.vue"))
    : null;
import { useMockup } from "@/composables/useMockup";
import { useI18n, type I18nKey } from "@/i18n";
import { toQueryScalar } from "@/utils/route";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const guild = useGuildStore();
const { t } = useI18n();

// Reactive — Vue Router reuses the component instance when navigating between guilds.
const guildId = computed(() => route.params.id as string | undefined);

const activeSection = computed(() => toQueryScalar(route.query.tab) ?? "server-overview");
const switcherOpen = ref(false);
const LG_BREAKPOINT = 1024;

// Persist sidebar state across refreshes; mobile always starts closed.
const sidebarOpen = ref(localStorage.getItem("sidebarOpen") !== "false");
onMounted(() => {
  if (window.innerWidth < LG_BREAKPOINT) sidebarOpen.value = false;
});
watch(sidebarOpen, (v) => localStorage.setItem("sidebarOpen", String(v)));

// Support mode: set by server via X-Support-Mode header on the first guild API call.
const supportMode = ref(false);
// True while probeGuildAccess is in flight — prevents activeComponent from redirecting
// away from the active tab before we know which tabs are available in support mode.
const probeLoading = ref(false);

async function probeGuildAccess(id: string | undefined) {
  if (!id || !auth.user?.is_operator) {
    supportMode.value = false;
    return;
  }
  probeLoading.value = true;
  const probeId = id;
  let newMode = false;
  let botGuild: BotGuildInfo | null = null;
  try {
    const { supportMode: serverMode } = await api.getWithHeaders<unknown>(`/guilds/${id}/language`);
    newMode = serverMode;
    if (newMode) {
      try {
        botGuild = await api.get<BotGuildInfo>(`/operator/guilds/${id}`);
      } catch {
        // non-critical — guild name may be unavailable if bot is offline
      }
    }
  } catch {
    // network error → treat as non-support access
  }
  if (guildId.value === probeId) {
    supportMode.value = newMode;
    if (newMode && botGuild) {
      // permission_level is hardcoded to "admin" here because effectiveLevel (in sectionGroups)
      // always uses "admin" as the fallback when supportMode is true, making this value irrelevant.
      // The tabs shown in support mode are governed solely by the supportMode flag, not permission_level.
      guild.setCurrent({
        id: botGuild.id,
        name: botGuild.name,
        icon: botGuild.icon,
        permission_level: "admin",
        bot_present: true,
        invite_url: null,
      });
    }
  }
  probeLoading.value = false;
}

// Reset to overview when switching guilds, clear mockup, and probe support mode
watch(guildId, (id) => {
  router.replace({ query: {} });
  clearMockup();
  probeGuildAccess(id);
});

onMounted(() => probeGuildAccess(guildId.value));
onUnmounted(() => clearMockup());

const { mockupLevel, clearMockup } = useMockup();

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

// Permission hierarchy: member < mod < admin < operator
const LEVEL_RANK: Record<string, number> = { member: 0, mod: 1, admin: 2, operator: 3 };

type SectionItem = {
  id: string;
  labelKey: I18nKey;
  icon: string;
  component: unknown;
  guildOnly?: boolean;
};

type SectionGroup = {
  id: string;
  labelKey: I18nKey;
  accentClass: string;
  operatorOnly?: boolean;
  /** Minimum permission level required to see this group. Defaults to "mod" if omitted. */
  minLevel?: "member" | "mod" | "admin";
  items: SectionItem[];
};

const allSectionGroups: SectionGroup[] = [
  {
    id: "general",
    labelKey: "nav.groups.general",
    accentClass: "text-blue-400",
    minLevel: "member",
    items: [
      { id: "server-overview", labelKey: "nav.items.server_overview", icon: "mdi:view-grid-outline", component: ServerOverviewTab },
      { id: "language", labelKey: "nav.items.language", icon: "mdi:translate", component: LanguageTab, guildOnly: true },
      { id: "reminders", labelKey: "nav.items.reminders", icon: "mdi:bell-outline", component: RemindersTab, guildOnly: true },
    ],
  },
  {
    id: "moderation",
    labelKey: "nav.groups.moderation",
    accentClass: "text-amber-400",
    items: [
      { id: "moderator-roles", labelKey: "nav.items.moderator_roles", icon: "mdi:shield-account", component: ModeratorRolesTab, guildOnly: true },
      { id: "auto-kicker", labelKey: "nav.items.auto_kicker", icon: "mdi:account-remove", component: AutoKickerTab, guildOnly: true },
      { id: "auto-delete", labelKey: "nav.items.auto_delete", icon: "mdi:delete-clock", component: AutoDeleteTab, guildOnly: true },
      { id: "leave-messages", labelKey: "nav.items.leave_messages", icon: "mdi:door-open", component: LeaveMessagesTab, guildOnly: true },
    ],
  },
  {
    id: "roles",
    labelKey: "nav.groups.roles",
    accentClass: "text-violet-400",
    items: [
      { id: "role-mappings", labelKey: "nav.items.role_mappings", icon: "mdi:account-switch", component: RoleMappingsTab, guildOnly: true },
      { id: "reaction-roles", labelKey: "nav.items.reaction_roles", icon: "mdi:emoticon-outline", component: ReactionRolesTab, guildOnly: true },
    ],
  },
  {
    id: "applications",
    labelKey: "nav.groups.applications",
    accentClass: "text-emerald-400",
    items: [
      { id: "application-forms", labelKey: "nav.items.application_forms", icon: "mdi:file-document-outline", component: ApplicationFormsTab, guildOnly: true },
      { id: "application-templates", labelKey: "nav.items.application_templates", icon: "mdi:file-document-multiple-outline", component: ApplicationTemplatesTab, guildOnly: true },
      { id: "application-submissions", labelKey: "nav.items.application_submissions", icon: "mdi:file-account-outline", component: ApplicationSubmissionsTab, guildOnly: true },
    ],
  },
  {
    id: "wow",
    labelKey: "nav.groups.wow",
    accentClass: "text-yellow-400",
    items: [
      { id: "wow-guild-news", labelKey: "nav.items.wow_guild_news", icon: "mdi:newspaper-variant-outline", component: WowGuildNewsTab, guildOnly: true },
      { id: "wow-crafting", labelKey: "nav.items.wow_crafting", icon: "mdi:hammer-wrench", component: WowCraftingTab, guildOnly: true },
    ],
  },
  {
    id: "support",
    labelKey: "nav.groups.support",
    accentClass: "text-cyan-400",
    minLevel: "member",
    items: [
      { id: "support", labelKey: "nav.items.support", icon: "mdi:message-text-outline", component: SupportTab },
    ],
  },
  {
    id: "operator",
    labelKey: "nav.groups.operator",
    accentClass: "text-rose-400",
    operatorOnly: true,
    items: [
      { id: "operator-dashboard", labelKey: "nav.items.operator_dashboard", icon: "mdi:heart-pulse", component: OperatorDashboardTab },
      { id: "operator-guilds", labelKey: "nav.items.operator_guilds", icon: "mdi:server-network-outline", component: OperatorGuildsTab },
      { id: "operator-modules", labelKey: "nav.items.operator_modules", icon: "mdi:puzzle-outline", component: OperatorModulesTab },
      { id: "operator-user-management", labelKey: "nav.items.operator_user_management", icon: "mdi:crown-outline", component: OperatorUserManagementTab },
    ],
  },
];

const sectionGroups = computed(() => {
  const effectiveIsOperator = mockupLevel.value === null && auth.user?.is_operator;
  const effectiveLevel = mockupLevel.value ?? guild.current?.permission_level ?? (supportMode.value ? "admin" : "member");

  return allSectionGroups
    .map((g) => ({ ...g, items: g.items.filter((item) => !item.guildOnly || !!guildId.value) }))
    .filter((g) => g.items.length > 0)
    .filter((g) => !g.operatorOnly || effectiveIsOperator)
    .filter((g) => (LEVEL_RANK[effectiveLevel] ?? 0) >= (LEVEL_RANK[g.minLevel ?? "mod"] ?? 0));
});

const allSections = computed(() => sectionGroups.value.flatMap((g) => g.items));
const activeComponent = computed(() => {
  // While the support-mode probe is in flight, the visible section list is incomplete.
  // Suppress the fallback redirect until we know the real set of available tabs.
  if (probeLoading.value) return undefined;
  const found = allSections.value.find((s) => s.id === activeSection.value);
  if (!found && allSections.value.length > 0) {
    // Requested tab is no longer available (filtered out) — fall back silently.
    router.replace({ query: { tab: allSections.value[0]!.id } });
    return allSections.value[0]!.component;
  }
  return found?.component;
});

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
    <div :class="['lg:hidden flex items-center h-12 px-4 border-b flex-shrink-0 bg-card gap-3', supportMode ? 'border-amber-500/50' : 'border-border']">
      <button
        class="text-muted-foreground hover:text-foreground transition-colors"
        :aria-label="t('nav.sidebar.open_nav')"
        @click="sidebarOpen = true"
      >
        <Icon icon="mdi:menu" class="w-5 h-5" />
      </button>
      <span class="font-semibold text-sm truncate">
        {{ guildId ? (guild.current?.name ?? t("nav.sidebar.guild_fallback")) : "NerpyBot" }}
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
          :title="sidebarOpen ? t('nav.sidebar.collapse') : t('nav.sidebar.expand')"
          :aria-label="sidebarOpen ? t('nav.sidebar.collapse') : t('nav.sidebar.expand')"
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
          :class="[
            'w-full flex items-center hover:bg-muted transition-colors text-left',
            sidebarOpen ? 'p-4 gap-2.5' : 'p-2 justify-center',
            { 'cursor-default': !guildId, 'ring-2 ring-inset ring-amber-500/50': supportMode },
          ]"
          @click="guildId ? (switcherOpen = !switcherOpen) : undefined"
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
            {{ guildId ? (guild.current?.name ?? t("nav.sidebar.guild_fallback")) : "NerpyBot" }}
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
            {{ t("nav.sidebar.all_servers") }}
          </button>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 p-2 overflow-y-auto" :class="sidebarOpen ? 'space-y-4' : 'space-y-2'">
        <div v-for="(group, idx) in sectionGroups" :key="group.id">
          <p v-if="sidebarOpen" :class="['px-3 pb-1 text-xs font-semibold uppercase tracking-wider', group.accentClass]">
            {{ t(group.labelKey) }}
          </p>
          <div v-else-if="idx > 0" class="border-t border-border/60 mx-1 mb-1.5" />
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
              :title="!sidebarOpen ? t(section.labelKey) : undefined"
              :aria-label="t(section.labelKey)"
              @click="navigateTo(section.id)"
            >
              <Icon :icon="section.icon" class="w-4 h-4 flex-shrink-0" />
              <span v-show="sidebarOpen">{{ t(section.labelKey) }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Sidebar footer -->
      <div class="flex flex-col flex-shrink-0">
        <component :is="TestModeIndicator" v-if="TestModeIndicator && sidebarOpen" />
        <div :class="['border-t border-border flex items-center', sidebarOpen ? 'p-4 gap-3' : 'p-2 justify-center']">
        <span v-show="sidebarOpen" class="text-sm text-muted-foreground truncate flex-1">
          {{ auth.user?.username }}
        </span>
        <LanguageSwitcher v-show="sidebarOpen" />
        <button
          class="p-2 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
          :title="t('nav.sidebar.logout')"
          :aria-label="t('nav.sidebar.logout')"
          @click="auth.clear(); router.push('/login')"
        >
          <Icon icon="mdi:logout" class="w-5 h-5" />
        </button>
        </div>
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
            <strong>{{ t("nav.sidebar.support_mode") }}</strong> — {{ t("nav.sidebar.support_mode_desc") }}
          </span>
        </div>
        <!-- Mockup toolbar (operator only) -->
        <MockupToolbar />
        <div class="max-w-4xl">
          <component :is="activeComponent" :guild-id="guildId" />
        </div>
      </main>
    </div>
  </div>
</template>
