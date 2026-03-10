<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type {
  WowGuildNewsSchema,
  WowCharacterMountSchema,
  WowGuildNewsCreate,
  WowGuildNewsUpdate,
  GuildValidateResult,
} from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import RealmPicker from "@/components/RealmPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";
import InfoTooltip from "@/components/InfoTooltip.vue";

const props = defineProps<{ guildId: string }>();

const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const trackers = ref<WowGuildNewsSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

// Per-tracker UI state
const editingId = ref<number | null>(null);
const editDraft = ref<WowGuildNewsUpdate>({});
const confirmDeleteId = ref<number | null>(null);
const rosterExpanded = ref<Record<number, boolean>>({});
const rosterData = ref<Record<number, WowCharacterMountSchema[]>>({});
const rosterLoading = ref<Record<number, boolean>>({});

// Add form
const showAdd = ref(false);
const newConfig = ref<Omit<WowGuildNewsCreate, "wow_guild_name"> & { wow_guild_name_input: string }>({
  channel_id: "",
  wow_guild_name_input: "",
  wow_realm_slug: "",
  region: "eu",
  active_days: 7,
  min_level: 10,
});
const addError = ref<string | null>(null);
const addSaving = ref(false);
const validateWarning = ref<string | null>(null);
const opError = ref<string | null>(null);

onMounted(() => {
  void load();
  void fetchChannels();
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const data = await api.get<{ guild_news: WowGuildNewsSchema[] }>(`/guilds/${props.guildId}/wow`);
    trackers.value = data.guild_news;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

// ── Enable/disable toggle ──

async function toggleEnabled(tracker: WowGuildNewsSchema) {
  const prev = tracker.enabled;
  tracker.enabled = !prev; // optimistic
  try {
    const updated = await api.patch<WowGuildNewsSchema>(
      `/guilds/${props.guildId}/wow/news-configs/${tracker.id}`,
      { enabled: !prev },
    );
    const idx = trackers.value.findIndex((t) => t.id === tracker.id);
    if (idx !== -1) trackers.value[idx] = updated;
  } catch {
    tracker.enabled = prev; // rollback
  }
}

// ── Edit ──

function startEdit(tracker: WowGuildNewsSchema) {
  editingId.value = tracker.id;
  editDraft.value = {
    channel_id: tracker.channel_id,
    active_days: tracker.active_days,
    min_level: tracker.min_level,
  };
}

function cancelEdit() {
  editingId.value = null;
  editDraft.value = {};
}

async function saveEdit(tracker: WowGuildNewsSchema) {
  opError.value = null;
  try {
    const updated = await api.patch<WowGuildNewsSchema>(
      `/guilds/${props.guildId}/wow/news-configs/${tracker.id}`,
      editDraft.value,
    );
    const idx = trackers.value.findIndex((t) => t.id === tracker.id);
    if (idx !== -1) trackers.value[idx] = updated;
    editingId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to save";
  }
}

// ── Delete ──

async function confirmDelete(id: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/wow/news-configs/${id}`);
    trackers.value = trackers.value.filter((t) => t.id !== id);
    confirmDeleteId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to delete";
  }
}

// ── Roster ──

async function toggleRoster(id: number) {
  if (rosterExpanded.value[id]) {
    rosterExpanded.value[id] = false;
    return;
  }
  rosterExpanded.value[id] = true;
  if (rosterData.value[id]) return; // already loaded
  rosterLoading.value[id] = true;
  try {
    rosterData.value[id] = await api.get<WowCharacterMountSchema[]>(
      `/guilds/${props.guildId}/wow/news-configs/${id}/roster`,
    );
  } catch {
    // Don't cache failure — leave rosterData[id] undefined so user can retry.
    rosterExpanded.value[id] = false;
  } finally {
    rosterLoading.value[id] = false;
  }
}

// ── Add tracker form ──

function resetAddForm() {
  newConfig.value = {
    channel_id: "",
    wow_guild_name_input: "",
    wow_realm_slug: "",
    region: "eu",
    active_days: 7,
    min_level: 10,
  };
  addError.value = null;
  validateWarning.value = null;
}

async function submitAdd() {
  addError.value = null;
  validateWarning.value = null;
  if (!newConfig.value.channel_id || !newConfig.value.wow_realm_slug || !newConfig.value.wow_guild_name_input) {
    addError.value = "Region, guild name, realm, and channel are required.";
    return;
  }

  addSaving.value = true;
  try {
    // Validate guild existence first
    try {
      const validation = await api.get<GuildValidateResult>(
        `/wow/guilds/validate?region=${newConfig.value.region}&realm=${newConfig.value.wow_realm_slug}&name=${encodeURIComponent(newConfig.value.wow_guild_name_input)}`,
      );
      if (!validation.valid) {
        addError.value = "Guild not found on this realm. Check the guild name and realm.";
        return;
      }
    } catch (e: unknown) {
      // 503 = bot offline; set warning and bail so user can "Save anyway"
      const status = (e as { status?: number })?.status;
      if (status === 503) {
        validateWarning.value = "Cannot verify guild (bot offline). Save anyway?";
        return;
      }
      // Other errors — still proceed
    }

    await doCreate();
  } catch (e: unknown) {
    addError.value = e instanceof Error ? e.message : "Failed to create tracker";
  } finally {
    addSaving.value = false;
  }
}

async function saveAnyway() {
  addSaving.value = true;
  validateWarning.value = null;
  try {
    await doCreate();
  } catch (e: unknown) {
    addError.value = e instanceof Error ? e.message : "Failed to create tracker";
  } finally {
    addSaving.value = false;
  }
}

async function doCreate() {
  const created = await api.post<WowGuildNewsSchema>(`/guilds/${props.guildId}/wow/news-configs`, {
    channel_id: newConfig.value.channel_id,
    wow_guild_name: newConfig.value.wow_guild_name_input,
    wow_realm_slug: newConfig.value.wow_realm_slug,
    region: newConfig.value.region,
    active_days: newConfig.value.active_days,
    min_level: newConfig.value.min_level,
  });
  trackers.value.push(created);
  showAdd.value = false;
  resetAddForm();
}

// ── Helpers ──

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">Guild News</h2>
        <p class="text-muted-foreground text-sm">Track a World of Warcraft guild's activity — boss kills, member joins and leaves, and achievements — and automatically post updates to a Discord channel. Each tracker targets one guild on a specific realm and only processes characters who have been active within the configured window.</p>
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors whitespace-nowrap flex-shrink-0"
        @click="showAdd = !showAdd; if (!showAdd) resetAddForm()"
      >
        {{ showAdd ? "Cancel" : "Add tracker" }}
      </button>
    </div>

    <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>

    <!-- Add tracker form -->
    <div v-if="showAdd" class="bg-card border border-border rounded p-4 space-y-3">
      <p class="text-sm font-medium">New tracker</p>
      <div class="grid grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            Region
            <InfoTooltip text="The WoW region your guild is on (EU or US). This determines which Blizzard API endpoint is queried." />
          </label>
          <select
            v-model="newConfig.region"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          >
            <option value="eu">EU</option>
            <option value="us">US</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            WoW Guild Name
            <InfoTooltip text="The exact in-game name of the WoW guild to track. The bot will verify this guild exists on the chosen realm before saving." />
          </label>
          <input
            v-model="newConfig.wow_guild_name_input"
            type="text"
            placeholder="Thunderfury"
            class="bg-input border border-border rounded px-3 py-2 text-sm"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            Realm
            <InfoTooltip text="The WoW realm (server) the guild is on. Must match the region selected above." />
          </label>
          <RealmPicker v-model="newConfig.wow_realm_slug" :region="newConfig.region" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            Channel
            <InfoTooltip text="The Discord channel where guild news updates will be posted. The bot must have permission to send messages there." />
          </label>
          <DiscordPicker v-model="newConfig.channel_id" :guild-id="guildId" kind="channel" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            Active days
            <InfoTooltip text="Only characters who have been seen in-game within this many days are considered active and included in news tracking." />
          </label>
          <input
            v-model.number="newConfig.active_days"
            type="number"
            min="1"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-24"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground flex items-center gap-1">
            Min level
            <InfoTooltip text="Characters below this level are ignored. Useful for filtering out low-level alts from news posts." />
          </label>
          <input
            v-model.number="newConfig.min_level"
            type="number"
            min="1"
            class="bg-input border border-border rounded px-3 py-2 text-sm w-24"
          />
        </div>
      </div>

      <p v-if="addError" class="text-destructive text-sm">{{ addError }}</p>

      <div v-if="validateWarning" class="flex items-center gap-3 text-sm text-yellow-400">
        <span>{{ validateWarning }}</span>
        <button
          class="underline hover:no-underline"
          :disabled="addSaving"
          @click="saveAnyway"
        >
          Save anyway
        </button>
      </div>

      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded text-sm font-medium disabled:opacity-50 transition-colors"
        :disabled="addSaving"
        @click="submitAdd"
      >
        {{ addSaving ? "Saving…" : "Add tracker" }}
      </button>
    </div>

    <!-- Tracker cards -->
    <div v-if="!loading" class="space-y-3">
      <p v-if="trackers.length === 0 && !showAdd" class="text-muted-foreground text-sm">
        No guild news trackers configured.
      </p>

      <div
        v-for="tracker in trackers"
        :key="tracker.id"
        class="bg-card border border-border rounded p-4 space-y-2"
      >
        <!-- Header row -->
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-medium text-sm truncate">
              {{ tracker.wow_guild_name }} — {{ tracker.wow_realm_slug }}-{{ tracker.region.toUpperCase() }}
            </span>
            <span
              :class="tracker.enabled ? 'bg-green-500/20 text-green-400' : 'bg-muted text-muted-foreground'"
              class="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
            >
              {{ tracker.enabled ? "Active" : "Disabled" }}
            </span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <button
              :class="tracker.enabled ? 'text-green-400 hover:text-green-300' : 'text-muted-foreground hover:text-foreground'"
              class="text-xs transition-colors"
              :title="tracker.enabled ? 'Disable' : 'Enable'"
              @click="toggleEnabled(tracker)"
            >
              <Icon :icon="tracker.enabled ? 'mdi:toggle-switch' : 'mdi:toggle-switch-off'" class="w-5 h-5" />
            </button>
            <button
              class="text-xs text-muted-foreground hover:text-foreground transition-colors"
              @click="editingId === tracker.id ? cancelEdit() : startEdit(tracker)"
            >
              {{ editingId === tracker.id ? "Cancel" : "Edit" }}
            </button>
            <button
              class="text-xs text-destructive hover:text-destructive/80 transition-colors"
              @click="confirmDeleteId = confirmDeleteId === tracker.id ? null : tracker.id"
            >
              Delete
            </button>
          </div>
        </div>

        <!-- Confirm delete -->
        <div v-if="confirmDeleteId === tracker.id" class="flex items-center gap-3 text-sm text-destructive">
          <span>Delete this tracker?</span>
          <button class="underline hover:no-underline" @click="confirmDelete(tracker.id)">Confirm</button>
          <button class="text-muted-foreground hover:text-foreground underline hover:no-underline" @click="confirmDeleteId = null">Cancel</button>
        </div>

        <!-- Edit form -->
        <div v-else-if="editingId === tracker.id" class="flex flex-wrap gap-2 items-end pt-1">
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1">
              Channel
              <InfoTooltip text="The Discord channel where guild news updates will be posted." />
            </label>
            <div class="w-48">
              <DiscordPicker v-model="editDraft.channel_id!" :guild-id="guildId" kind="channel" />
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1">
              Active days
              <InfoTooltip text="Only characters who have been seen in-game within this many days are considered active and included in news tracking." />
            </label>
            <input
              v-model.number="editDraft.active_days"
              type="number"
              min="1"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-20"
            />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-muted-foreground flex items-center gap-1">
              Min level
              <InfoTooltip text="Characters below this level are ignored. Useful for filtering out low-level alts from news posts." />
            </label>
            <input
              v-model.number="editDraft.min_level"
              type="number"
              min="1"
              class="bg-input border border-border rounded px-3 py-2 text-sm w-20"
            />
          </div>
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-2 rounded text-sm font-medium transition-colors"
            @click="saveEdit(tracker)"
          >
            Save
          </button>
        </div>

        <!-- Stats row -->
        <div v-else class="text-muted-foreground text-xs flex flex-wrap gap-3">
          <span>#{{ channelName(tracker.channel_id) }}</span>
          <span>Last news: {{ relativeTime(tracker.last_activity) }}</span>
          <span>{{ tracker.tracked_characters }} tracked characters</span>
          <span>Active days: {{ tracker.active_days }}</span>
          <span>Min level: {{ tracker.min_level }}</span>
        </div>

        <!-- Roster toggle -->
        <div v-if="editingId !== tracker.id && confirmDeleteId !== tracker.id">
          <button
            class="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
            @click="toggleRoster(tracker.id)"
          >
            <Icon
              :icon="rosterExpanded[tracker.id] ? 'mdi:chevron-down' : 'mdi:chevron-right'"
              class="w-3.5 h-3.5"
            />
            {{ rosterExpanded[tracker.id] ? "Hide roster" : "Show roster" }}
          </button>

          <div v-if="rosterExpanded[tracker.id]" class="mt-2">
            <div v-if="rosterLoading[tracker.id]" class="text-xs text-muted-foreground">Loading roster…</div>
            <p v-else-if="!rosterData[tracker.id]?.length" class="text-xs text-muted-foreground">No character data yet.</p>
            <table v-else class="w-full text-xs border-collapse">
              <thead>
                <tr class="text-muted-foreground border-b border-border">
                  <th class="text-left py-1.5 pr-4 font-medium">Character</th>
                  <th class="text-left py-1.5 pr-4 font-medium">Realm</th>
                  <th class="text-left py-1.5 pr-4 font-medium">Mounts</th>
                  <th class="text-left py-1.5 font-medium">Last checked</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="char in rosterData[tracker.id]"
                  :key="`${char.character_name}-${char.realm_slug}`"
                  class="border-t border-border hover:bg-muted/20 transition-colors"
                >
                  <td class="py-1.5 pr-4">{{ char.character_name }}</td>
                  <td class="py-1.5 pr-4 text-muted-foreground">{{ char.realm_slug }}</td>
                  <td class="py-1.5 pr-4">{{ char.mount_count }}</td>
                  <td class="py-1.5 text-muted-foreground">{{ relativeTime(char.last_checked) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
