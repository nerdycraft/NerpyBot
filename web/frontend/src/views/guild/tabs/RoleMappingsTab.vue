<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { RoleMappingSchema } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import InfoTooltip from "@/components/InfoTooltip.vue";

const props = defineProps<{ guildId: string }>();

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
    error.value = e instanceof Error ? e.message : "Failed to load";
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
    error.value = e instanceof Error ? e.message : "Failed to add mapping";
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
    error.value = e instanceof Error ? e.message : "Failed to remove mapping";
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Role Mappings</h2>
      <p class="text-muted-foreground text-sm">
        Delegate role assignment to specific roles — each mapping grants members of the source role the ability to give
        the target role to others via bot commands. Multiple mappings can share the same source or target role.
      </p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else class="space-y-4">
      <p v-if="mappings.length === 0 && !error" class="text-muted-foreground text-sm">
        No role mappings configured.
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
          Remove
        </button>
      </div>

      <div class="flex flex-wrap gap-2 items-end mt-4">
        <div class="w-44 flex flex-col gap-1.5">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Source role
            <InfoTooltip text="The role whose members are allowed to assign the target role to others using bot commands." />
          </label>
          <DiscordPicker v-model="newMapping.source_role_id" :guild-id="guildId" kind="role" placeholder="Source role…" />
        </div>
        <span class="text-muted-foreground pb-2">→</span>
        <div class="w-44 flex flex-col gap-1.5">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Target role
            <InfoTooltip text="The role that will be assigned to members when a user with the source role runs the assign command." />
          </label>
          <DiscordPicker v-model="newMapping.target_role_id" :guild-id="guildId" kind="role" placeholder="Target role…" />
        </div>
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="adding || !newMapping.source_role_id.trim() || !newMapping.target_role_id.trim()"
          @click="add"
        >
          {{ adding ? "Adding…" : "Add" }}
        </button>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>
  </div>
</template>
