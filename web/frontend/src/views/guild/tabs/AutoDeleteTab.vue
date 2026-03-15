<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { AutoDeleteRule } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();
const { t } = useI18n();

const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const rules = ref<AutoDeleteRule[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const newRule = ref({
  channel_id: "",
  keep_messages: 0,
  delete_older_than: 0,
  delete_pinned: false,
  enabled: true,
});
const adding = ref(false);

onMounted(() => {
  void load();
  void fetchChannels();
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    rules.value = await api.get<AutoDeleteRule[]>(`/guilds/${props.guildId}/auto-delete`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
}

async function add() {
  if (!newRule.value.channel_id.trim()) return;
  adding.value = true;
  error.value = null;
  try {
    await api.post(`/guilds/${props.guildId}/auto-delete`, { ...newRule.value });
    newRule.value = { channel_id: "", keep_messages: 0, delete_older_than: 0, delete_pinned: false, enabled: true };
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    adding.value = false;
  }
}

async function toggleEnabled(rule: AutoDeleteRule) {
  error.value = null;
  try {
    const updated = await api.put<AutoDeleteRule>(`/guilds/${props.guildId}/auto-delete/${rule.id}`, {
      enabled: !rule.enabled,
    });
    const idx = rules.value.findIndex((r) => r.id === rule.id);
    if (idx !== -1) rules.value[idx] = updated;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.save_failed");
  }
}

async function remove(id: number) {
  error.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/auto-delete/${id}`);
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.auto_delete.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.auto_delete.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>

    <div v-else class="space-y-4">
      <p v-if="rules.length === 0 && !error" class="text-muted-foreground text-sm">
        {{ t("tabs.auto_delete.empty") }}
      </p>

      <div
        v-for="rule in rules"
        :key="rule.id"
        class="bg-card border border-border rounded p-4 space-y-2"
      >
        <div class="flex items-center justify-between">
          <span class="text-sm">#{{ channelName(rule.channel_id) }}</span>
          <div class="flex gap-3 text-sm">
            <button
              :class="rule.enabled ? 'text-green-400 hover:text-green-300' : 'text-muted-foreground hover:text-foreground'"
              class="transition-colors"
              @click="toggleEnabled(rule)"
            >
              {{ rule.enabled ? t("common.enabled") : t("common.disabled") }}
            </button>
            <button class="text-destructive hover:text-destructive/80 transition-colors" @click="remove(rule.id)">
              {{ t("common.delete") }}
            </button>
          </div>
        </div>
        <div class="text-muted-foreground text-xs flex flex-wrap gap-4">
          <span>{{ t("tabs.auto_delete.keep_display", { count: rule.keep_messages }) }}</span>
          <span>{{ t("tabs.auto_delete.older_display", { seconds: rule.delete_older_than }) }}</span>
          <span>{{ t("tabs.auto_delete.delete_pinned_display", { value: rule.delete_pinned ? t("common.yes") : t("common.no") }) }}</span>
        </div>
      </div>

      <!-- Add form -->
      <div class="bg-card border border-border rounded p-4 space-y-3">
        <p class="text-sm font-medium">{{ t("tabs.auto_delete.add_rule") }}</p>
        <div class="flex flex-wrap gap-2 items-end">
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1">
              {{ t("tabs.auto_delete.channel_label") }}
              <InfoTooltip :text="t('tabs.auto_delete.channel_tooltip')" />
            </label>
            <div class="w-48">
              <DiscordPicker v-model="newRule.channel_id" :guild-id="guildId" kind="channel" />
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1" for="ad-keep">
              {{ t("tabs.auto_delete.keep_label") }}
              <InfoTooltip :text="t('tabs.auto_delete.keep_tooltip')" />
            </label>
            <input id="ad-keep" v-model.number="newRule.keep_messages" type="number" min="0"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1" for="ad-older">
              {{ t("tabs.auto_delete.older_label") }}
              <InfoTooltip :text="t('tabs.auto_delete.older_tooltip')" />
            </label>
            <input id="ad-older" v-model.number="newRule.delete_older_than" type="number" min="0"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-28" />
          </div>
          <label class="flex items-center gap-2 text-sm pb-2">
            <input type="checkbox" v-model="newRule.delete_pinned" />
            <span class="flex items-center gap-1">
              {{ t("tabs.auto_delete.delete_pinned_label") }}
              <InfoTooltip :text="t('tabs.auto_delete.delete_pinned_tooltip')" />
            </span>
          </label>
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors pb-2"
            :disabled="adding || !newRule.channel_id.trim()"
            @click="add"
          >
            {{ adding ? t("common.adding") : t("common.add") }}
          </button>
        </div>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>
  </div>
</template>
