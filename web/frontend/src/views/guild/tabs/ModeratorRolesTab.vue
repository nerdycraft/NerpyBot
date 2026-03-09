<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { ModeratorRole } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const roles = ref<ModeratorRole[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);
const newRoleId = ref("");
const adding = ref(false);

onMounted(load);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    roles.value = await api.get<ModeratorRole[]>(`/guilds/${props.guildId}/moderator-roles`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

async function add() {
  const roleId = newRoleId.value.trim();
  if (!roleId) return;
  adding.value = true;
  error.value = null;
  try {
    await api.post(`/guilds/${props.guildId}/moderator-roles`, { role_id: roleId });
    newRoleId.value = "";
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to add role";
  } finally {
    adding.value = false;
  }
}

async function remove(roleId: string) {
  error.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/moderator-roles/${roleId}`);
    await load();
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to remove role";
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Moderator Roles</h2>
      <p class="text-muted-foreground text-sm">Discord roles granted bot moderator permissions.</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <div v-else class="space-y-4">
      <p v-if="roles.length === 0 && !error" class="text-muted-foreground text-sm">
        No moderator roles configured.
      </p>

      <div
        v-for="role in roles"
        :key="role.role_id"
        class="flex items-center justify-between bg-card border border-border rounded px-4 py-3"
      >
        <span class="font-mono text-sm">{{ role.role_id }}</span>
        <button
          class="text-destructive hover:text-destructive/80 text-sm transition-colors"
          @click="remove(role.role_id)"
        >
          Remove
        </button>
      </div>

      <div class="flex gap-2 mt-4">
        <input
          v-model="newRoleId"
          type="text"
          placeholder="Role ID"
          class="bg-input border border-border rounded px-3 py-2 text-sm flex-1 min-w-0"
          @keyup.enter="add"
        />
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors flex-shrink-0"
          :disabled="adding || !newRoleId.trim()"
          @click="add"
        >
          {{ adding ? "Adding…" : "Add" }}
        </button>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    </div>
  </div>
</template>
