<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ApplicationFormSchema, ApplicationSubmissionSchema } from "@/api/types";

const props = defineProps<{ guildId: string }>();
const route = useRoute();

const forms = ref<ApplicationFormSchema[]>([]);
const submissions = ref<ApplicationSubmissionSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const selectedId = ref<number | null>(null);
const statusFilter = ref<string>("");
const formFilter = ref<number | null>(null);

const STATUS_LABELS: Record<string, string> = {
  "": "All",
  pending: "Pending",
  approved: "Approved",
  denied: "Denied",
};

const STATUS_BADGES: Record<string, string> = {
  pending: "bg-yellow-400/10 text-yellow-400 border-yellow-400/20",
  approved: "bg-green-400/10 text-green-400 border-green-400/20",
  denied: "bg-destructive/10 text-destructive border-destructive/20",
};

const filtered = computed(() =>
  submissions.value.filter((s) => {
    if (statusFilter.value && s.status !== statusFilter.value) return false;
    if (formFilter.value !== null && s.form_name !== forms.value.find((f) => f.id === formFilter.value)?.name)
      return false;
    return true;
  }),
);

const selected = computed<ApplicationSubmissionSchema | null>(() =>
  selectedId.value !== null ? (submissions.value.find((s) => s.id === selectedId.value) ?? null) : null,
);

const approvers = computed(() => selected.value?.votes.filter((v) => v.vote === "approve") ?? []);
const deniers = computed(() => selected.value?.votes.filter((v) => v.vote === "deny") ?? []);

onMounted(async () => {
  const preselected = route.query.formId ? Number(route.query.formId) : null;
  try {
    const subUrl = preselected !== null
      ? `/guilds/${props.guildId}/application-submissions?form_id=${preselected}`
      : `/guilds/${props.guildId}/application-submissions`;
    const [formData, subData] = await Promise.all([
      api.get<ApplicationFormSchema[]>(`/guilds/${props.guildId}/application-forms`),
      api.get<ApplicationSubmissionSchema[]>(subUrl),
    ]);
    forms.value = formData;
    submissions.value = subData;
    if (preselected !== null) formFilter.value = preselected;
    if (subData.length > 0) selectedId.value = subData[0]!.id;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
});

// Re-filter when navigating here from "View Submissions" while the tab is already mounted
watch(() => route.query.formId, (newId) => {
  if (newId !== undefined) void applyFormFilter(Number(newId));
});

async function applyFormFilter(id: number | null) {
  formFilter.value = id;
  loading.value = true;
  error.value = null;
  try {
    const url =
      id !== null
        ? `/guilds/${props.guildId}/application-submissions?form_id=${id}`
        : `/guilds/${props.guildId}/application-submissions`;
    submissions.value = await api.get<ApplicationSubmissionSchema[]>(url);
    selectedId.value = submissions.value.length > 0 ? submissions.value[0]!.id : null;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

function formatDate(iso: string) {
  return iso.slice(0, 16).replace("T", " ");
}
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-lg font-semibold">Submissions</h2>
      <p class="text-muted-foreground text-sm">Browse all application submissions from server members, including their answers, current status, and reviewer votes. This view is read-only — approvals and denials are cast by moderators directly in the review channel on Discord.</p>
    </div>

    <div v-if="loading && submissions.length === 0" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else class="flex gap-4 min-h-0" style="height: calc(100vh - 260px)">
      <!-- Left panel: list + filters -->
      <aside class="w-72 flex-shrink-0 border border-border rounded flex flex-col overflow-hidden">
        <!-- Form filter -->
        <div class="flex-shrink-0 p-2 border-b border-border">
          <label class="text-sm font-medium flex items-center gap-1.5 mb-1">
            Form
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="Filter submissions to show only those belonging to a specific application form." />
          </label>
          <select
            class="w-full bg-input border border-border rounded px-2 py-1.5 text-sm"
            :value="formFilter ?? ''"
            @change="applyFormFilter(($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
          >
            <option value="">All forms</option>
            <option v-for="f in forms" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
        </div>

        <!-- Status filter -->
        <div class="flex-shrink-0 p-2 border-b border-border">
          <label class="text-sm font-medium flex items-center gap-1.5 mb-1">
            Status
            <Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground cursor-help" title="Filter submissions by their current review status: pending awaiting votes, approved by moderators, or denied." />
          </label>
          <div class="flex gap-1 flex-wrap">
            <button
              v-for="(label, value) in STATUS_LABELS"
              :key="value"
              :class="[
                'px-2.5 py-1 rounded text-xs transition-colors',
                statusFilter === value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted',
              ]"
              @click="statusFilter = value"
            >
              {{ label }}
            </button>
          </div>
        </div>

        <!-- List -->
        <div class="flex-1 overflow-y-auto">
          <p v-if="filtered.length === 0" class="p-4 text-muted-foreground text-sm">No submissions.</p>
          <button
            v-for="sub in filtered"
            :key="sub.id"
            :class="[
              'w-full text-left px-4 py-3 border-b border-border transition-colors',
              selectedId === sub.id ? 'bg-muted' : 'hover:bg-muted/50',
            ]"
            @click="selectedId = sub.id"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-medium truncate">{{ sub.user_name ?? sub.user_id }}</span>
              <span
                :class="['text-xs capitalize border rounded-full px-1.5 py-0.5 flex-shrink-0', STATUS_BADGES[sub.status] ?? 'text-muted-foreground']"
              >{{ sub.status }}</span>
            </div>
            <div class="text-xs text-muted-foreground mt-0.5 truncate">
              <span v-if="sub.form_name" class="mr-1">{{ sub.form_name }} ·</span>
              {{ formatDate(sub.submitted_at) }}
            </div>
          </button>
        </div>
      </aside>

      <!-- Right panel: detail -->
      <main class="flex-1 overflow-y-auto">
        <p v-if="!selected" class="text-muted-foreground text-sm">Select a submission to view details.</p>

        <div v-else class="max-w-2xl space-y-6">
          <!-- Applicant header -->
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 class="text-lg font-semibold">{{ selected.user_name ?? selected.user_id }}</h2>
              <p class="text-sm text-muted-foreground">
                <span v-if="selected.form_name" class="mr-1">{{ selected.form_name }} ·</span>
                Submitted {{ formatDate(selected.submitted_at) }}
              </p>
            </div>
            <span
              :class="[
                'text-sm capitalize border rounded-full px-3 py-1 font-medium flex-shrink-0',
                STATUS_BADGES[selected.status] ?? 'text-muted-foreground',
              ]"
            >{{ selected.status }}</span>
          </div>

          <!-- Decision reason -->
          <div v-if="selected.decision_reason" class="bg-muted/50 rounded px-4 py-3 text-sm">
            <p class="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wider">Decision Reason</p>
            <p>{{ selected.decision_reason }}</p>
          </div>

          <!-- Answers -->
          <div class="space-y-4">
            <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Answers</h3>
            <div
              v-for="answer in selected.answers"
              :key="answer.question_id"
              class="space-y-1"
            >
              <p class="text-xs font-medium text-muted-foreground">{{ answer.question_text }}</p>
              <p class="text-sm bg-card border border-border rounded px-3 py-2 whitespace-pre-wrap">{{ answer.answer_text }}</p>
            </div>
            <p v-if="selected.answers.length === 0" class="text-muted-foreground text-sm">No answers.</p>
          </div>

          <!-- Votes -->
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Votes</h3>
            <p v-if="selected.votes.length === 0" class="text-muted-foreground text-sm">No votes recorded.</p>
            <div v-else class="flex flex-wrap gap-6">
              <div v-if="approvers.length > 0" class="space-y-1.5">
                <p class="text-xs text-green-400 font-medium">Approved ({{ approvers.length }})</p>
                <div
                  v-for="v in approvers"
                  :key="v.voter_id"
                  class="flex items-center gap-1.5 text-sm"
                >
                  <Icon icon="mdi:check-circle" class="w-4 h-4 text-green-400 flex-shrink-0" />
                  <span>{{ v.voter_name ?? v.voter_id }}</span>
                </div>
              </div>
              <div v-if="deniers.length > 0" class="space-y-1.5">
                <p class="text-xs text-destructive font-medium">Denied ({{ deniers.length }})</p>
                <div
                  v-for="v in deniers"
                  :key="v.voter_id"
                  class="flex items-center gap-1.5 text-sm"
                >
                  <Icon icon="mdi:close-circle" class="w-4 h-4 text-destructive flex-shrink-0" />
                  <span>{{ v.voter_name ?? v.voter_id }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>
