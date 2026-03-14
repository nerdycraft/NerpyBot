<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { api } from "@/api/client";
import type { LeaveMessageConfig } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useManualSave } from "@/composables/useManualSave";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();
const { t } = useI18n();

const config = ref<LeaveMessageConfig | null>(null);
const loading = ref(true);
const { saving, error, success, dirty, ready, save } = useManualSave(config, (c) =>
  api.put<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`, {
    channel_id: c.channel_id,
    message: c.message,
    enabled: c.enabled,
  }),
);

let _loadSeq = 0;

async function loadConfig() {
  const seq = ++_loadSeq;
  ready.value = false;
  loading.value = true;
  error.value = null;
  config.value = null;
  try {
    const next = await api.get<LeaveMessageConfig>(`/guilds/${props.guildId}/leave-messages`);
    if (seq !== _loadSeq) return;
    config.value = next;
  } catch (e: unknown) {
    if (seq !== _loadSeq) return;
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  }
  if (seq !== _loadSeq) return;
  loading.value = false;
  await nextTick();
  ready.value = true;
}

watch(
  () => props.guildId,
  () => void loadConfig(),
  { immediate: true },
);
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.leave_messages.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.leave_messages.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>

    <div v-else-if="config" class="space-y-4">
      <label class="flex items-center gap-3 cursor-pointer">
        <input type="checkbox" v-model="config.enabled" class="w-4 h-4" />
        <span class="text-sm font-medium flex items-center gap-1.5">
          {{ t("common.enabled") }}
          <InfoTooltip :text="t('tabs.leave_messages.enabled_tooltip')" />
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5">
          {{ t("tabs.leave_messages.channel_label") }}
          <InfoTooltip :text="t('tabs.leave_messages.channel_tooltip')" />
        </label>
        <div class="w-64">
          <DiscordPicker
            :model-value="config.channel_id ?? ''"
            :guild-id="guildId"
            kind="channel"
            @update:model-value="config.channel_id = $event || null"
          />
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium flex items-center gap-1.5" for="leave-message">
          {{ t("tabs.leave_messages.message_label") }}
          <InfoTooltip :text="t('tabs.leave_messages.message_tooltip')" />
        </label>
        <textarea
          id="leave-message"
          v-model="config.message"
          rows="3"
          :placeholder="t('tabs.leave_messages.placeholder')"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-full resize-y"
        />
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
      <div class="flex items-center gap-3">
        <button
          :disabled="!dirty || saving"
          class="px-4 py-1.5 text-sm font-medium rounded bg-primary text-primary-foreground disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          @click="save"
        >
          {{ saving ? t("common.saving") : t("common.save") }}
        </button>
        <span v-if="success" class="text-xs text-green-400">{{ t("common.saved") }}</span>
      </div>
    </div>

    <p v-else class="text-destructive text-sm">{{ error }}</p>
  </div>
</template>
