<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { PremiumUserSchema } from "@/api/types";

const premiumUsers = ref<PremiumUserSchema[]>([]);
const newUserId = ref("");
const grantError = ref<string | null>(null);
const granting = ref(false);

onMounted(async () => {
  try {
    premiumUsers.value = await api.get<PremiumUserSchema[]>("/operator/premium-users");
  } catch {
    // non-critical
  }
});

async function grantPremium() {
  const id = newUserId.value.trim();
  if (!id) return;
  grantError.value = null;
  granting.value = true;
  try {
    const created = await api.post<PremiumUserSchema>("/operator/premium-users", { user_id: id });
    if (!premiumUsers.value.find((u) => u.user_id === created.user_id)) {
      premiumUsers.value.push(created);
    }
    newUserId.value = "";
  } catch (e: unknown) {
    grantError.value = e instanceof Error ? e.message : "Failed to grant access";
  } finally {
    granting.value = false;
  }
}

async function revokePremium(userId: string) {
  grantError.value = null;
  try {
    await api.delete(`/operator/premium-users/${userId}`);
    premiumUsers.value = premiumUsers.value.filter((u) => u.user_id !== userId);
  } catch (e: unknown) {
    grantError.value = e instanceof Error ? e.message : "Failed to revoke access";
  }
}

function formatDate(iso: string) {
  return iso.slice(0, 10);
}
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-1">
      <Icon icon="mdi:crown-outline" class="w-5 h-5 text-yellow-400" />
      <h2 class="text-xl font-bold">User Management</h2>
    </div>
    <p class="text-muted-foreground text-sm mb-6">
      Grant or revoke dashboard access. Users without premium status are redirected to the login
      page.
    </p>

    <p v-if="grantError" class="text-destructive text-sm mb-3">{{ grantError }}</p>

    <!-- Current premium users -->
    <div class="space-y-1.5 mb-6">
      <p v-if="premiumUsers.length === 0" class="text-muted-foreground text-sm">
        No premium users yet.
      </p>
      <div
        v-for="u in premiumUsers"
        :key="u.user_id"
        class="flex items-center gap-3 bg-card border border-border rounded px-3 py-2 text-sm group"
      >
        <Icon icon="mdi:account-outline" class="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <span class="font-mono text-xs flex-1">{{ u.user_id }}</span>
        <span class="text-xs text-muted-foreground flex-shrink-0">since {{ formatDate(u.granted_at) }}</span>
        <button
          class="text-xs text-destructive hover:text-destructive/80 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 flex items-center gap-1"
          @click="revokePremium(u.user_id)"
        >
          <Icon icon="mdi:close" class="w-3.5 h-3.5" />
          Revoke
        </button>
      </div>
    </div>

    <!-- Grant access form -->
    <div class="flex gap-2 items-end">
      <div class="flex flex-col gap-1">
        <label class="text-xs text-muted-foreground">Discord User ID</label>
        <input
          v-model="newUserId"
          placeholder="e.g. 123456789012345678"
          class="bg-input border border-border rounded px-3 py-1.5 text-sm font-mono w-56"
          @keyup.enter="grantPremium"
        />
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors flex items-center gap-1.5"
        :disabled="!newUserId.trim() || granting"
        @click="grantPremium"
      >
        <Icon icon="mdi:crown-plus-outline" class="w-4 h-4" />
        {{ granting ? "Granting…" : "Grant Access" }}
      </button>
    </div>
  </div>
</template>
