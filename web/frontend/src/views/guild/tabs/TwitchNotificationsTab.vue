<!-- web/frontend/src/views/guild/tabs/TwitchNotificationsTab.vue -->
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { TwitchNotificationCreate, TwitchNotificationSchema, TwitchNotificationUpdate } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();

const { t } = useI18n();
const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const notifications = ref<TwitchNotificationSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const opError = ref<string | null>(null);

// Add form
const showAdd = ref(false);
const addSaving = ref(false);
const addError = ref<string | null>(null);
const newConfig = ref<TwitchNotificationCreate>({ channel_id: "", streamer: "", notify_offline: false });

// Edit state
const editingId = ref<number | null>(null);
const editDraft = ref<TwitchNotificationUpdate>({});

// Delete state
const confirmDeleteId = ref<number | null>(null);

onMounted(() => {
  void load();
  void fetchChannels();
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await api.get<TwitchNotificationSchema[]>(`/guilds/${props.guildId}/twitch-notifications`);
    notifications.value = data;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
}

async function saveAdd() {
  addSaving.value = true;
  addError.value = null;
  try {
    const created = await api.post<TwitchNotificationSchema>(
      `/guilds/${props.guildId}/twitch-notifications`,
      newConfig.value,
    );
    notifications.value.push(created);
    showAdd.value = false;
    newConfig.value = { channel_id: "", streamer: "", notify_offline: false };
  } catch (e: unknown) {
    addError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    addSaving.value = false;
  }
}

function startEdit(n: TwitchNotificationSchema) {
  editingId.value = n.id;
  editDraft.value = { channel_id: n.channel_id, message: n.message, notify_offline: n.notify_offline };
}

async function saveEdit(n: TwitchNotificationSchema) {
  opError.value = null;
  try {
    const updated = await api.patch<TwitchNotificationSchema>(
      `/guilds/${props.guildId}/twitch-notifications/${n.id}`,
      editDraft.value,
    );
    const idx = notifications.value.findIndex((x) => x.id === n.id);
    if (idx !== -1) notifications.value[idx] = updated;
    editingId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  }
}

async function deleteNotification(id: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/twitch-notifications/${id}`);
    notifications.value = notifications.value.filter((n) => n.id !== id);
    confirmDeleteId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-xl font-bold">{{ t("nav.items.twitch_notifications") }}</h2>
        <p class="text-sm text-gray-400">{{ t("twitch.tab_subtitle") }}</p>
      </div>
      <button
        class="px-3 py-1.5 rounded text-sm font-medium text-white"
        style="background-color: #9146ff"
        @click="showAdd = !showAdd"
      >
        + {{ t("twitch.add_button") }}
      </button>
    </div>

    <!-- Add form -->
    <div v-if="showAdd" class="mb-4 p-4 rounded-lg bg-gray-800 border border-gray-600">
      <h3 class="font-semibold mb-3">{{ t("twitch.add_button") }}</h3>
      <div class="mb-3">
        <label class="block text-xs uppercase text-gray-400 mb-1">{{ t("twitch.streamer_label") }}</label>
        <input
          v-model="newConfig.streamer"
          class="w-full rounded bg-gray-700 border border-gray-500 px-3 py-2 text-sm"
          :placeholder="t('twitch.streamer_hint')"
        />
      </div>
      <div class="mb-3">
        <label class="block text-xs uppercase text-gray-400 mb-1">{{ t("twitch.channel_label") }}</label>
        <DiscordPicker v-model="newConfig.channel_id" :guild-id="guildId" kind="channel" />
      </div>
      <div class="mb-3">
        <label class="block text-xs uppercase text-gray-400 mb-1">{{ t("twitch.message_label") }}</label>
        <input
          v-model="newConfig.message"
          class="w-full rounded bg-gray-700 border border-gray-500 px-3 py-2 text-sm"
          :placeholder="t('twitch.message_hint')"
        />
      </div>
      <div class="mb-4 flex items-center gap-2">
        <input id="add-notify-offline" v-model="newConfig.notify_offline" type="checkbox" />
        <label for="add-notify-offline" class="text-sm text-gray-300">{{ t("twitch.notify_offline_label") }}</label>
      </div>
      <div v-if="addError" class="text-red-400 text-sm mb-2">{{ addError }}</div>
      <div class="flex gap-2">
        <button
          class="px-3 py-1.5 rounded text-sm font-medium text-white"
          style="background-color: #9146ff"
          :disabled="addSaving || !newConfig.streamer || !newConfig.channel_id"
          @click="saveAdd"
        >
          {{ addSaving ? t("common.saving") : t("common.save") }}
        </button>
        <button class="px-3 py-1.5 rounded text-sm border border-gray-500 text-gray-300" @click="showAdd = false">
          {{ t("common.cancel") }}
        </button>
      </div>
    </div>

    <!-- Loading / error -->
    <div v-if="loading" class="text-gray-400">{{ t("common.loading") }}</div>
    <div v-else-if="error" class="text-red-400">{{ error }}</div>

    <!-- Empty state -->
    <div v-else-if="notifications.length === 0" class="text-center py-12 text-gray-400">
      <div class="text-4xl mb-2">📡</div>
      <div>{{ t("twitch.empty") }}</div>
    </div>

    <!-- Notification list -->
    <div v-else>
      <div v-if="opError" class="text-red-400 text-sm mb-2">{{ opError }}</div>
      <div v-for="n in notifications" :key="n.id" class="mb-3 p-4 rounded-lg border border-gray-600 bg-gray-800">
        <div v-if="editingId === n.id">
          <!-- Edit mode -->
          <div class="mb-2">
            <label class="block text-xs uppercase text-gray-400 mb-1">{{ t("twitch.channel_label") }}</label>
            <DiscordPicker v-model="editDraft.channel_id!" :guild-id="guildId" kind="channel" />
          </div>
          <div class="mb-2">
            <label class="block text-xs uppercase text-gray-400 mb-1">{{ t("twitch.message_label") }}</label>
            <input
              v-model="editDraft.message"
              class="w-full rounded bg-gray-700 border border-gray-500 px-3 py-2 text-sm"
            />
          </div>
          <div class="mb-3 flex items-center gap-2">
            <input :id="`edit-offline-${n.id}`" v-model="editDraft.notify_offline" type="checkbox" />
            <label :for="`edit-offline-${n.id}`" class="text-sm text-gray-300">{{
              t("twitch.notify_offline_label")
            }}</label>
          </div>
          <div class="flex gap-2">
            <button class="px-3 py-1 rounded text-sm bg-indigo-600 text-white" @click="saveEdit(n)">
              {{ t("common.save") }}
            </button>
            <button
              class="px-3 py-1 rounded text-sm border border-gray-500 text-gray-300"
              @click="editingId = null"
            >
              {{ t("common.cancel") }}
            </button>
          </div>
        </div>
        <div v-else-if="confirmDeleteId === n.id">
          <p class="text-sm text-gray-300 mb-3">
            Delete notification for <strong>{{ n.streamer_display_name }}</strong>?
          </p>
          <div class="flex gap-2">
            <button class="px-3 py-1 rounded text-sm bg-red-700 text-white" @click="deleteNotification(n.id)">
              {{ t("common.confirm") }}
            </button>
            <button
              class="px-3 py-1 rounded text-sm border border-gray-500 text-gray-300"
              @click="confirmDeleteId = null"
            >
              {{ t("common.cancel") }}
            </button>
          </div>
        </div>
        <div v-else class="flex justify-between items-center">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="font-semibold" style="color: #9146ff">{{ n.streamer_display_name }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full bg-green-900 text-green-300">{{
                t("twitch.active_badge")
              }}</span>
            </div>
            <div class="text-sm text-gray-400">
              {{ t("twitch.channel_label_short") }} {{ channelName(n.channel_id) }}
              &middot;
              {{ t("twitch.offline_notify_label") }}
              {{ n.notify_offline ? t("twitch.offline_yes") : t("twitch.offline_no") }}
            </div>
            <div v-if="n.message" class="text-xs text-gray-500 mt-1 italic">"{{ n.message }}"</div>
            <div v-else class="text-xs text-gray-600 mt-1">{{ t("twitch.default_message") }}</div>
          </div>
          <div class="flex gap-2">
            <button
              class="px-2 py-1 rounded text-sm border border-gray-500 text-gray-300"
              @click="startEdit(n)"
            >
              {{ t("common.edit") }}
            </button>
            <button
              class="px-2 py-1 rounded text-sm border border-red-800 text-red-400"
              @click="confirmDeleteId = n.id"
            >
              {{ t("common.delete") }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
