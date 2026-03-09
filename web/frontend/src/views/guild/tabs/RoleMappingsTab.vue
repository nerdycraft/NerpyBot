<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { RoleMappingSchema } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const mappings = ref<RoleMappingSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const newMapping = ref({ source_role_id: "", target_role_id: "" });
const adding = ref(false);

onMounted(load);

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
      <p class="text-muted-foreground text-sm">Allow a role to assign another role to members.</p>
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
        <span class="font-mono text-sm">{{ m.source_role_id }} → {{ m.target_role_id }}</span>
        <button
          class="text-destructive hover:text-destructive/80 text-sm transition-colors"
          @click="remove(m.id)"
        >
          Remove
        </button>
      </div>

      <div class="flex flex-wrap gap-2 items-center mt-4">
        <input
          v-model="newMapping.source_role_id"
          type="text"
          placeholder="Source Role ID"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-40"
        />
        <span class="text-muted-foreground">→</span>
        <input
          v-model="newMapping.target_role_id"
          type="text"
          placeholder="Target Role ID"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-40"
        />
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
