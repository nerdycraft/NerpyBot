<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { RoleMappingSchema } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();
const { t } = useI18n();

const { fetchRoles, roleName } = useGuildEntities(props.guildId);

const mappings = ref<RoleMappingSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const newMapping = ref({ source_role_id: "", target_role_id: "" });
const adding = ref(false);

onMounted(() => { void load(); void fetchRoles(); });

async function load() {
  loading.value = true;
  error.value = null;
  try {
    mappings.value = await api.get<RoleMappingSchema[]>(`/guilds/${props.guildId}/role-mappings`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.load_failed");
  } finally {
    loading.value = false;
  }
}

async function add() {
  const src = newMapping.value.source_role_id.trim();
  const tgt = newMapping.value.target_role_id.trim();
  if (!src || !tgt) return;
  adding.value = true;
  error.value = null;
  try {
    await api.post(`/guilds/${props.guildId}/role-mappings`, { source_role_id: src, target_role_id: tgt });
    newMapping.value = { source_role_id: "", target_role_id: "" };
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    adding.value = false;
  }
}

async function remove(id: number) {
  error.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/role-mappings/${id}`);
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.role_mappings.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.role_mappings.desc") }}</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>

    <div v-else class="space-y-4">
      <p v-if="mappings.length === 0 && !error" class="text-muted-foreground text-sm">
        {{ t("tabs.role_mappings.empty") }}
      </p>

      <div
        v-for="m in mappings"
        :key="m.id"
        class="flex items-center justify-between bg-card border border-border rounded px-4 py-3"
      >
        <span class="text-sm">@{{ roleName(m.source_role_id) }} → @{{ roleName(m.target_role_id) }}</span>
        <button
          class="text-destructive hover:text-destructive/80 text-sm transition-colors"
          @click="remove(m.id)"
        >
          {{ t("common.remove") }}
        </button>
      </div>

      <div class="flex flex-wrap gap-2 items-end mt-4">
        <div class="w-44 flex flex-col gap-1.5">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.role_mappings.source_label") }}
            <InfoTooltip :text="t('tabs.role_mappings.source_tooltip')" />
          </label>
          <DiscordPicker v-model="newMapping.source_role_id" :guild-id="guildId" kind="role" :placeholder="t('tabs.role_mappings.source_placeholder')" />
        </div>
        <span class="text-muted-foreground pb-2">→</span>
        <div class="w-44 flex flex-col gap-1.5">
          <label class="text-sm font-medium flex items-center gap-1.5">
            {{ t("tabs.role_mappings.target_label") }}
            <InfoTooltip :text="t('tabs.role_mappings.target_tooltip')" />
          </label>
          <DiscordPicker v-model="newMapping.target_role_id" :guild-id="guildId" kind="role" :placeholder="t('tabs.role_mappings.target_placeholder')" />
        </div>
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="adding || !newMapping.source_role_id.trim() || !newMapping.target_role_id.trim()"
          @click="add"
        >
          {{ adding ? t("common.adding") : t("common.add") }}
        </button>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>
  </div>
</template>
