<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { ReactionRoleMessageSchema } from "@/api/types";
import { useGuildEntities } from "@/composables/useGuildEntities";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();
const { t } = useI18n();

const { fetchChannels, fetchRoles, channelName, roleName } = useGuildEntities(props.guildId);

const messages = ref<ReactionRoleMessageSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  void fetchChannels();
  void fetchRoles();
  try {
    messages.value = await api.get<ReactionRoleMessageSchema[]>(`/guilds/${props.guildId}/reaction-roles`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.reaction_roles.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.reaction_roles.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="messages.length === 0" class="text-muted-foreground text-sm">
      {{ t("tabs.reaction_roles.empty") }}
    </p>

    <div v-else class="space-y-3">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="bg-card border border-border rounded px-4 py-3 space-y-2"
      >
        <div class="text-sm text-muted-foreground">
          {{ t("tabs.reaction_roles.message_ref", { channel: channelName(msg.channel_id), id: msg.message_id }) }}
        </div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="entry in msg.entries"
            :key="entry.role_id"
            class="bg-muted rounded px-2 py-1 text-xs"
          >
            {{ entry.emoji }} → @{{ roleName(entry.role_id) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
