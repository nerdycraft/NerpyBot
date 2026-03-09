<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { useAuthStore } from "@/stores/auth";
import { api } from "@/api/client";
import type { GuildSummary, PremiumUserSchema, UserInfo } from "@/api/types";

const auth = useAuthStore();
const router = useRouter();

const managedGuilds = computed(() => auth.guilds.filter((g) => g.bot_present));
const invitableGuilds = computed(() => auth.guilds.filter((g) => !g.bot_present));

// ── Operator: premium user management ──
const premiumUsers = ref<PremiumUserSchema[]>([]);
const newUserId = ref("");
const grantError = ref<string | null>(null);
const granting = ref(false);

// Always refresh guild data on mount — ensures bot_present and invite_url are current
// even when the user object was restored from localStorage with stale field values.
onMounted(async () => {
  try {
    const me = await api.get<UserInfo>("/auth/me");
    auth.setUser(me);
  } catch {
    // silently ignore — stale cached data is better than a broken page
  }
  if (auth.user?.is_operator) {
    try {
      premiumUsers.value = await api.get<PremiumUserSchema[]>("/operator/premium-users");
    } catch {
      // non-critical
    }
  }
});

function select(guildId: string) {
  router.push(`/guilds/${guildId}`);
}

function iconUrl(guild: GuildSummary): string | null {
  if (!guild.icon) return null;
  return `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`;
}

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
  <div class="min-h-screen p-8">
    <div class="max-w-5xl mx-auto">

      <!-- Managed servers -->
      <h1 class="text-2xl font-bold mb-2">Your Servers</h1>
      <p class="text-muted-foreground mb-6">Select a server to manage its settings.</p>

      <div v-if="managedGuilds.length === 0" class="text-muted-foreground mb-8">
        NerpyBot is not in any of your servers yet.
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
        <button
          v-for="guild in managedGuilds"
          :key="guild.id"
          class="bg-card hover:bg-muted rounded-lg p-5 flex items-center gap-4 text-left transition-colors border border-border hover:border-primary"
          @click="select(guild.id)"
        >
          <img
            v-if="iconUrl(guild)"
            :src="iconUrl(guild)!"
            :alt="guild.name"
            class="w-12 h-12 rounded-full object-cover flex-shrink-0"
          />
          <div
            v-else
            class="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-lg font-bold flex-shrink-0"
            aria-hidden="true"
          >
            {{ guild.name.charAt(0).toUpperCase() }}
          </div>
          <div class="min-w-0">
            <div class="font-semibold truncate">{{ guild.name }}</div>
            <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
          </div>
        </button>
      </div>

      <!-- Invitable servers -->
      <template v-if="invitableGuilds.length > 0">
        <h2 class="text-lg font-semibold mb-2">Add to a Server</h2>
        <p class="text-muted-foreground mb-6">
          You have sufficient permissions to invite NerpyBot to these servers.
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
          <div
            v-for="guild in invitableGuilds"
            :key="guild.id"
            class="bg-card rounded-lg p-5 flex items-center gap-4 border border-border opacity-75"
          >
            <img
              v-if="iconUrl(guild)"
              :src="iconUrl(guild)!"
              :alt="guild.name"
              class="w-12 h-12 rounded-full object-cover flex-shrink-0"
            />
            <div
              v-else
              class="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-lg font-bold flex-shrink-0"
              aria-hidden="true"
            >
              {{ guild.name.charAt(0).toUpperCase() }}
            </div>
            <div class="min-w-0 flex-1">
              <div class="font-semibold truncate">{{ guild.name }}</div>
              <div class="text-xs text-muted-foreground capitalize">{{ guild.permission_level }}</div>
            </div>
            <a
              v-if="guild.invite_url"
              :href="guild.invite_url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-xs font-medium px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:opacity-90 transition-opacity whitespace-nowrap"
            >
              Invite Bot
            </a>
          </div>
        </div>
      </template>

      <!-- Operator: premium user management -->
      <template v-if="auth.user?.is_operator">
        <div class="border-t border-border pt-8">
          <div class="flex items-center gap-2 mb-1">
            <Icon icon="mdi:crown-outline" class="w-5 h-5 text-yellow-400" />
            <h2 class="text-lg font-semibold">Premium Users</h2>
          </div>
          <p class="text-muted-foreground text-sm mb-6">
            Grant or revoke dashboard access. Users without premium status are redirected to the login page.
          </p>

          <p v-if="grantError" class="text-destructive text-sm mb-3">{{ grantError }}</p>

          <!-- Current premium users -->
          <div class="space-y-1.5 mb-4">
            <p v-if="premiumUsers.length === 0" class="text-muted-foreground text-sm">No premium users yet.</p>
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

    </div>
  </div>
</template>
