<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { AutoDeleteRule } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";

const props = defineProps<{ guildId: string }>();

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

onMounted(() => { void load(); void fetchChannels(); });

async function load() {
  loading.value = true;
  error.value = null;
  try {
    rules.value = await api.get<AutoDeleteRule[]>(`/guilds/${props.guildId}/auto-delete`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
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
    error.value = e instanceof Error ? e.message : "Failed to add rule";
  } finally {
    adding.value = false;
  }
}

async function toggleEnabled(rule: AutoDeleteRule) {
  error.value = null;
  try {
    const updated = await api.put<AutoDeleteRule>(
      `/guilds/${props.guildId}/auto-delete/${rule.id}`,
      { enabled: !rule.enabled },
    );
    const idx = rules.value.findIndex((r) => r.id === rule.id);
    if (idx !== -1) rules.value[idx] = updated;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to update rule";
  }
}

async function remove(id: number) {
  error.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/auto-delete/${id}`);
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to delete rule";
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Auto-Delete</h2>
      <p class="text-muted-foreground text-sm">
        Automatically deletes messages in specific channels once they exceed a configured age or message count.
        Each rule targets one channel — add as many rules as needed, and toggle them on or off without deleting them.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else class="space-y-4">
      <p v-if="rules.length === 0 && !error" class="text-muted-foreground text-sm">
        No auto-delete rules configured.
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
              {{ rule.enabled ? "Enabled" : "Disabled" }}
            </button>
            <button class="text-destructive hover:text-destructive/80 transition-colors" @click="remove(rule.id)">
              Delete
            </button>
          </div>
        </div>
        <div class="text-muted-foreground text-xs flex flex-wrap gap-4">
          <span>Keep: {{ rule.keep_messages }} msgs</span>
          <span>Older than: {{ rule.delete_older_than }}s</span>
          <span>Delete pinned: {{ rule.delete_pinned ? "Yes" : "No" }}</span>
        </div>
      </div>

      <!-- Add form -->
      <div class="bg-card border border-border rounded p-4 space-y-3">
        <p class="text-sm font-medium">Add Rule</p>
        <div class="flex flex-wrap gap-2 items-end">
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1">
              Channel
              <Icon icon="mdi:information-outline" class="w-3 h-3 cursor-help" title="The channel where auto-deletion will be applied. Each channel can only have one rule." />
            </label>
            <div class="w-48">
              <DiscordPicker v-model="newRule.channel_id" :guild-id="guildId" kind="channel" />
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1" for="ad-keep">
              Keep msgs
              <Icon icon="mdi:information-outline" class="w-3 h-3 cursor-help" title="Always keep at least this many recent messages in the channel, regardless of age. Set to 0 to disable." />
            </label>
            <input id="ad-keep" v-model.number="newRule.keep_messages" type="number" min="0"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1" for="ad-older">
              Older than (s)
              <Icon icon="mdi:information-outline" class="w-3 h-3 cursor-help" title="Delete messages older than this many seconds. Set to 0 to only use the keep-count limit." />
            </label>
            <input id="ad-older" v-model.number="newRule.delete_older_than" type="number" min="0"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-28" />
          </div>
          <label class="flex items-center gap-2 text-sm pb-2">
            <input type="checkbox" v-model="newRule.delete_pinned" />
            <span class="flex items-center gap-1">
              Delete pinned
              <Icon icon="mdi:information-outline" class="w-3 h-3 text-muted-foreground cursor-help" title="When enabled, pinned messages in this channel are also subject to deletion. By default, pinned messages are kept." />
            </span>
          </label>
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors pb-2"
            :disabled="adding || !newRule.channel_id.trim()"
            @click="add"
          >
            {{ adding ? "Adding…" : "Add" }}
          </button>
        </div>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>
  </div>
</template>
