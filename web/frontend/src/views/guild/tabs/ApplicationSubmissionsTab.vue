<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/api/client";
import type { ApplicationFormSchema, ApplicationSubmissionSchema } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { type I18nKey, useI18n } from "@/i18n";
import { formatDatetime } from "@/utils/date";
import { toQueryScalar } from "@/utils/route";

const props = defineProps<{ guildId: string }>();
const route = useRoute();

const { t } = useI18n();

function setLoadError(e: unknown) {
  error.value = e instanceof Error ? e.message : t("common.load_failed");
}

const forms = ref<ApplicationFormSchema[]>([]);
const submissions = ref<ApplicationSubmissionSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const selectedId = ref<number | null>(null);
const statusFilter = ref<string>("");
const formFilter = ref<number | null>(null);

const STATUS_LABEL_KEYS: Record<string, I18nKey> = {
  "": "tabs.application_submissions.status.all",
  pending: "tabs.application_submissions.status.pending",
  approved: "tabs.application_submissions.status.approved",
  denied: "tabs.application_submissions.status.denied",
};

const STATUS_BADGES: Record<string, string> = {
  pending: "bg-yellow-400/10 text-yellow-400 border-yellow-400/20",
  approved: "bg-green-400/10 text-green-400 border-green-400/20",
  denied: "bg-destructive/10 text-destructive border-destructive/20",
};

const filtered = computed(() =>
  statusFilter.value ? submissions.value.filter((s) => s.status === statusFilter.value) : submissions.value,
);

const selected = computed<ApplicationSubmissionSchema | null>(() =>
  selectedId.value !== null ? (filtered.value.find((s) => s.id === selectedId.value) ?? null) : null,
);

watch(filtered, (items) => {
  if (!items.some((s) => s.id === selectedId.value)) {
    selectedId.value = items[0]?.id ?? null;
  }
});

const approvers = computed(() => selected.value?.votes.filter((v) => v.vote === "approve") ?? []);
const deniers = computed(() => selected.value?.votes.filter((v) => v.vote === "deny") ?? []);

onMounted(async () => {
  const rawFormId = toQueryScalar(route.query.formId);
  const parsed = rawFormId ? Number(rawFormId) : NaN;
  const preselected = Number.isFinite(parsed) ? parsed : null;
  try {
    const subUrl =
      preselected !== null
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
    setLoadError(e);
  } finally {
    loading.value = false;
  }
});

// Re-filter when navigating here from "View Submissions" while the tab is already mounted
watch(
  () => route.query.formId,
  (newId) => {
    const id = toQueryScalar(newId);
    const n = id ? Number(id) : NaN;
    void applyFormFilter(Number.isFinite(n) ? n : null);
  },
);

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
    setLoadError(e);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.application_submissions.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.application_submissions.desc") }}</p>
    </div>

    <div v-if="loading && submissions.length === 0" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <div v-else class="flex gap-4 min-h-0" style="height: calc(100vh - 260px)">
      <!-- Left panel: list + filters -->
      <aside class="w-72 flex-shrink-0 border border-border rounded flex flex-col overflow-hidden">
        <!-- Form filter -->
        <div class="flex-shrink-0 p-2 border-b border-border">
          <label class="text-sm font-medium flex items-center gap-1.5 mb-1">
            {{ t("tabs.application_submissions.form_label") }}
            <InfoTooltip :text="t('tabs.application_submissions.form_tooltip')" />
          </label>
          <select
            class="w-full bg-input border border-border rounded px-2 py-1.5 text-sm"
            :value="formFilter ?? ''"
            @change="applyFormFilter(($event.target as HTMLSelectElement).value ? Number(($event.target as HTMLSelectElement).value) : null)"
          >
            <option value="">{{ t("tabs.application_submissions.all_forms") }}</option>
            <option v-for="f in forms" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
        </div>

        <!-- Status filter -->
        <div class="flex-shrink-0 p-2 border-b border-border">
          <label class="text-sm font-medium flex items-center gap-1.5 mb-1">
            {{ t("tabs.application_submissions.status_label") }}
            <InfoTooltip :text="t('tabs.application_submissions.status_tooltip')" />
          </label>
          <div class="flex gap-1 flex-wrap">
            <button
              v-for="(labelKey, value) in STATUS_LABEL_KEYS"
              :key="value"
              :class="[
                'px-2.5 py-1 rounded text-xs transition-colors',
                statusFilter === value
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted',
              ]"
              @click="statusFilter = value"
            >
              {{ t(labelKey) }}
            </button>
          </div>
        </div>

        <!-- List -->
        <div class="flex-1 overflow-y-auto">
          <p v-if="filtered.length === 0" class="p-4 text-muted-foreground text-sm">{{ t("tabs.application_submissions.empty") }}</p>
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
                :class="['text-xs border rounded-full px-1.5 py-0.5 flex-shrink-0', STATUS_BADGES[sub.status] ?? 'text-muted-foreground']"
              >{{ STATUS_LABEL_KEYS[sub.status] ? t(STATUS_LABEL_KEYS[sub.status]!) : sub.status }}</span>
            </div>
            <div class="text-xs text-muted-foreground mt-0.5 truncate">
              <span v-if="sub.form_name" class="mr-1">{{ sub.form_name }} ·</span>
              {{ formatDatetime(sub.submitted_at) }}
            </div>
          </button>
        </div>
      </aside>

      <!-- Right panel: detail -->
      <main class="flex-1 overflow-y-auto">
        <p v-if="!selected" class="text-muted-foreground text-sm">{{ t("tabs.application_submissions.select_hint") }}</p>

        <div v-else class="max-w-2xl space-y-6">
          <!-- Applicant header -->
          <div class="flex items-start justify-between gap-4">
            <div>
              <h2 class="text-lg font-semibold">{{ selected.user_name ?? selected.user_id }}</h2>
              <p class="text-sm text-muted-foreground">
                <span v-if="selected.form_name" class="mr-1">{{ selected.form_name }} ·</span>
                {{ t("tabs.application_submissions.submitted", { datetime: formatDatetime(selected.submitted_at) }) }}
              </p>
            </div>
            <span
              :class="[
                'text-sm border rounded-full px-3 py-1 font-medium flex-shrink-0',
                STATUS_BADGES[selected.status] ?? 'text-muted-foreground',
              ]"
            >{{ STATUS_LABEL_KEYS[selected.status] ? t(STATUS_LABEL_KEYS[selected.status]!) : selected.status }}</span>
          </div>

          <!-- Decision reason -->
          <div v-if="selected.decision_reason" class="bg-muted/50 rounded px-4 py-3 text-sm">
            <p class="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wider">{{ t("tabs.application_submissions.decision_reason") }}</p>
            <p>{{ selected.decision_reason }}</p>
          </div>

          <!-- Answers -->
          <div class="space-y-4">
            <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider">{{ t("tabs.application_submissions.answers") }}</h3>
            <div
              v-for="answer in selected.answers"
              :key="answer.question_id"
              class="space-y-1"
            >
              <p class="text-xs font-medium text-muted-foreground">{{ answer.question_text }}</p>
              <p class="text-sm bg-card border border-border rounded px-3 py-2 whitespace-pre-wrap">{{ answer.answer_text }}</p>
            </div>
            <p v-if="selected.answers.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.application_submissions.no_answers") }}</p>
          </div>

          <!-- Votes -->
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wider">{{ t("tabs.application_submissions.votes") }}</h3>
            <p v-if="selected.votes.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.application_submissions.no_votes") }}</p>
            <div v-else class="flex flex-wrap gap-6">
              <div v-if="approvers.length > 0" class="space-y-1.5">
                <p class="text-xs text-green-400 font-medium">{{ t("tabs.application_submissions.approved_count", { count: approvers.length }) }}</p>
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
                <p class="text-xs text-destructive font-medium">{{ t("tabs.application_submissions.denied_count", { count: deniers.length }) }}</p>
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
