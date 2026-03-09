<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useGuildStore } from "@/stores/guild";
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

const tabs = [
  { id: "language", label: "Language", component: LanguageTab },
  { id: "moderator-roles", label: "Moderator Roles", component: ModeratorRolesTab },
  { id: "leave-messages", label: "Leave Messages", component: LeaveMessagesTab },
  { id: "auto-delete", label: "Auto-Delete", component: AutoDeleteTab },
  { id: "auto-kicker", label: "Auto-Kicker", component: AutoKickerTab },
  { id: "role-mappings", label: "Role Mappings", component: RoleMappingsTab },
  { id: "reminders", label: "Reminders", component: RemindersTab },
  { id: "reaction-roles", label: "Reaction Roles", component: ReactionRolesTab },
  { id: "wow", label: "WoW", component: WowTab },
] as const;

const activeTabId = ref<string>(tabs[0].id);
const guildId = route.params.id as string;

function activeComponent() {
  return tabs.find((t) => t.id === activeTabId.value)?.component;
}
</script>

<template>
  <div class="min-h-screen p-8">
    <div class="max-w-4xl mx-auto">
      <!-- Header -->
      <div class="flex items-center gap-4 mb-8">
        <button
          class="text-muted-foreground hover:text-foreground transition-colors text-sm"
          @click="router.push('/guilds')"
        >
          ← Back
        </button>
        <h1 class="text-2xl font-bold">{{ guild.current?.name ?? "Guild Settings" }}</h1>
      </div>

      <!-- Tab bar -->
      <div class="flex flex-wrap gap-1 mb-6 border-b border-border pb-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="[
            'px-4 py-2 rounded-t text-sm font-medium transition-colors',
            activeTabId === tab.id
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground',
          ]"
          @click="activeTabId = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Active tab content -->
      <component :is="activeComponent()" :guild-id="guildId" />
    </div>
  </div>
</template>
