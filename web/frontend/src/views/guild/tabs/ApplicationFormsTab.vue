<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ApplicationFormSchema } from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";
import { useGuildEntities } from "@/composables/useGuildEntities";

const props = defineProps<{ guildId: string }>();

const router = useRouter();
const { fetchChannels, channelName } = useGuildEntities(props.guildId);

const forms = ref<ApplicationFormSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const expandedFormId = ref<number | null>(null);
const editingFormId = ref<number | null>(null);
const showCreateForm = ref(false);

const editingQuestionId = ref<number | null>(null);
const editQuestionText = ref("");
const newQuestionText = ref<Record<number, string>>({});

const saving = ref(false);
const opError = ref<string | null>(null);
const questionSavedFormId = ref<number | null>(null);
let flashTimer: ReturnType<typeof setTimeout> | null = null;

function flashQuestionSaved(formId: number) {
  questionSavedFormId.value = formId;
  flashTimer = setTimeout(() => { questionSavedFormId.value = null; }, 1800);
}

onUnmounted(() => {
  if (flashTimer !== null) clearTimeout(flashTimer);
});

function blankForm() {
  return {
    name: "",
    required_approvals: 1,
    required_denials: 1,
    review_channel_id: "" as string,
    apply_channel_id: "" as string,
    approval_message: "",
    denial_message: "",
    apply_description: "",
  };
}
const formDraft = ref(blankForm());

onMounted(() => { void load(); void fetchChannels(); });

async function load() {
  loading.value = true;
  error.value = null;
  try {
    forms.value = await api.get<ApplicationFormSchema[]>(`/guilds/${props.guildId}/application-forms`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

function startEdit(form: ApplicationFormSchema) {
  editingFormId.value = form.id;
  formDraft.value = {
    name: form.name,
    required_approvals: form.required_approvals,
    required_denials: form.required_denials,
    review_channel_id: form.review_channel_id ?? "",
    apply_channel_id: form.apply_channel_id ?? "",
    approval_message: form.approval_message ?? "",
    denial_message: form.denial_message ?? "",
    apply_description: form.apply_description ?? "",
  };
}

function startCreate() {
  formDraft.value = blankForm();
  showCreateForm.value = true;
  editingFormId.value = null;
  expandedFormId.value = null;
}

async function saveForm() {
  saving.value = true;
  opError.value = null;
  try {
    const body = {
      name: formDraft.value.name.trim(),
      required_approvals: formDraft.value.required_approvals,
      required_denials: formDraft.value.required_denials,
      review_channel_id: formDraft.value.review_channel_id || null,
      apply_channel_id: formDraft.value.apply_channel_id || null,
      approval_message: formDraft.value.approval_message || null,
      denial_message: formDraft.value.denial_message || null,
      apply_description: formDraft.value.apply_description || null,
    };
    if (editingFormId.value !== null) {
      const updated = await api.put<ApplicationFormSchema>(`/guilds/${props.guildId}/application-forms/${editingFormId.value}`, body);
      const idx = forms.value.findIndex((f) => f.id === editingFormId.value);
      if (idx !== -1) forms.value[idx] = updated;
      editingFormId.value = null;
    } else {
      const created = await api.post<ApplicationFormSchema>(`/guilds/${props.guildId}/application-forms`, body);
      forms.value.push(created);
      showCreateForm.value = false;
      expandedFormId.value = created.id;
    }
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Save failed";
  } finally {
    saving.value = false;
  }
}

async function deleteForm(formId: number) {
  if (!confirm("Delete this form and all its submissions?")) return;
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-forms/${formId}`);
    forms.value = forms.value.filter((f) => f.id !== formId);
    if (expandedFormId.value === formId) expandedFormId.value = null;
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Delete failed";
  }
}

async function addQuestion(formId: number) {
  const text = (newQuestionText.value[formId] ?? "").trim();
  if (!text) return;
  opError.value = null;
  try {
    const q = await api.post(`/guilds/${props.guildId}/application-forms/${formId}/questions`, { question_text: text });
    const form = forms.value.find((f) => f.id === formId);
    if (form) form.questions.push(q as never);
    newQuestionText.value[formId] = "";
    flashQuestionSaved(formId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to add question";
  }
}

async function saveQuestion(formId: number, questionId: number) {
  opError.value = null;
  try {
    const updated = await api.put(`/guilds/${props.guildId}/application-forms/${formId}/questions/${questionId}`, {
      question_text: editQuestionText.value.trim(),
    });
    const form = forms.value.find((f) => f.id === formId);
    if (form) {
      const idx = form.questions.findIndex((q) => q.id === questionId);
      if (idx !== -1) form.questions[idx] = updated as never;
    }
    editingQuestionId.value = null;
    flashQuestionSaved(formId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to update question";
  }
}

async function deleteQuestion(formId: number, questionId: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-forms/${formId}/questions/${questionId}`);
    const form = forms.value.find((f) => f.id === formId);
    if (form) form.questions = form.questions.filter((q) => q.id !== questionId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to delete question";
  }
}

</script>

<template>
  <div class="space-y-8">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">Forms</h2>
        <p class="text-muted-foreground text-sm">Application forms define the questions members answer when applying via the bot in DMs. Each form needs at least one question and a review channel where moderators cast approve/deny votes.</p>
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
        @click="startCreate"
      >
        <Icon icon="mdi:plus" class="w-4 h-4" />
        New Form
      </button>
    </div>

    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <!-- Create Form Panel -->
    <div v-if="showCreateForm" class="bg-card border border-primary rounded p-4 space-y-3">
      <p class="text-sm font-semibold">New Form</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Name
            <span title="A unique, human-readable name for this form shown in the dashboard and on the Apply button embed." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <input v-model="formDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm" placeholder="e.g. Guild Application" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Review Channel
            <span title="The Discord channel where the bot posts submission embeds and where moderators cast approve/deny votes." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <DiscordPicker v-model="formDraft.review_channel_id" :guild-id="guildId" kind="channel" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Apply Channel
            <span title="The Discord channel where the bot posts the persistent Apply button that members click to start their application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <DiscordPicker v-model="formDraft.apply_channel_id" :guild-id="guildId" kind="channel" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Apply Description
            <span title="Optional text displayed on the Apply button embed to describe the application or set expectations for applicants." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <textarea v-model="formDraft.apply_description" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Required Approvals
            <span title="Number of moderator approve votes needed to automatically accept the application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <input v-model.number="formDraft.required_approvals" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Required Denials
            <span title="Number of moderator deny votes needed to automatically reject the application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <input v-model.number="formDraft.required_denials" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Approval Message
            <span title="Optional message the bot sends to the applicant via DM when their application is approved." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <textarea v-model="formDraft.approval_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-sm font-medium flex items-center gap-1.5">
            Denial Message
            <span title="Optional message the bot sends to the applicant via DM when their application is denied." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
          </label>
          <textarea v-model="formDraft.denial_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
        </div>
      </div>
      <div class="flex gap-2">
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="saving || !formDraft.name.trim()"
          @click="saveForm"
        >{{ saving ? "Saving…" : "Create" }}</button>
        <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="showCreateForm = false">Cancel</button>
      </div>
    </div>

    <!-- Forms List -->
    <div v-if="!loading && !error" class="space-y-3">
      <p v-if="forms.length === 0" class="text-muted-foreground text-sm">No forms yet.</p>

      <div v-for="form in forms" :key="form.id" class="bg-card border border-border rounded overflow-hidden">
        <div class="flex items-center gap-3 px-4 py-3">
          <button class="flex-1 flex items-center gap-3 text-left" @click="expandedFormId = expandedFormId === form.id ? null : form.id">
            <Icon
              :icon="expandedFormId === form.id ? 'mdi:chevron-down' : 'mdi:chevron-right'"
              class="w-4 h-4 text-muted-foreground flex-shrink-0"
            />
            <span class="font-medium text-sm">{{ form.name }}</span>
            <span class="text-xs text-muted-foreground">{{ form.questions.length }} questions · ✓{{ form.required_approvals }} ✗{{ form.required_denials }}</span>
          </button>
          <button class="text-xs text-muted-foreground hover:text-foreground transition-colors" @click="startEdit(form); expandedFormId = form.id">Edit</button>
          <button class="text-xs text-destructive hover:text-destructive/80 transition-colors" @click="deleteForm(form.id)">Delete</button>
        </div>

        <div v-if="expandedFormId === form.id" class="border-t border-border px-4 py-4 space-y-5">
          <!-- Inline edit panel -->
          <div v-if="editingFormId === form.id" class="space-y-3 pb-3 border-b border-border">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Edit Settings</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Name
                  <span title="A unique, human-readable name for this form shown in the dashboard and on the Apply button embed." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <input v-model="formDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Review Channel
                  <span title="The Discord channel where the bot posts submission embeds and where moderators cast approve/deny votes." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <DiscordPicker v-model="formDraft.review_channel_id" :guild-id="guildId" kind="channel" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Apply Channel
                  <span title="The Discord channel where the bot posts the persistent Apply button that members click to start their application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <DiscordPicker v-model="formDraft.apply_channel_id" :guild-id="guildId" kind="channel" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Apply Description
                  <span title="Optional text displayed on the Apply button embed to describe the application or set expectations for applicants." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <textarea v-model="formDraft.apply_description" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Required Approvals
                  <span title="Number of moderator approve votes needed to automatically accept the application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <input v-model.number="formDraft.required_approvals" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Required Denials
                  <span title="Number of moderator deny votes needed to automatically reject the application." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <input v-model.number="formDraft.required_denials" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Approval Message
                  <span title="Optional message the bot sends to the applicant via DM when their application is approved." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <textarea v-model="formDraft.approval_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-sm font-medium flex items-center gap-1.5">
                  Denial Message
                  <span title="Optional message the bot sends to the applicant via DM when their application is denied." class="cursor-help inline-flex"><Icon icon="mdi:information-outline" class="w-3.5 h-3.5 text-muted-foreground" /></span>
                </label>
                <textarea v-model="formDraft.denial_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
              </div>
            </div>
            <div class="flex gap-2">
              <button
                class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
                :disabled="saving"
                @click="saveForm"
              >{{ saving ? "Saving…" : "Save" }}</button>
              <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="editingFormId = null">Cancel</button>
            </div>
          </div>

          <!-- Settings summary (when not editing) -->
          <div v-else class="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
            <span v-if="form.review_channel_id">Review channel: #{{ channelName(form.review_channel_id) }}</span>
            <span v-if="form.apply_channel_id">Apply channel: #{{ channelName(form.apply_channel_id) }}</span>
            <span v-if="form.approval_message">Approval message set</span>
            <span v-if="form.denial_message">Denial message set</span>
          </div>

          <!-- Questions -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Questions</p>
              <span v-if="questionSavedFormId === form.id" class="text-xs text-green-400 transition-opacity">✓ Saved</span>
            </div>
            <p v-if="form.questions.length === 0" class="text-muted-foreground text-xs">No questions yet.</p>
            <div v-else class="rounded border border-border/50 divide-y divide-border/50">
              <div
                v-for="q in [...form.questions].sort((a, b) => a.sort_order - b.sort_order)"
                :key="q.id"
                class="flex items-center gap-2 group px-3 py-2.5 hover:bg-muted/30 transition-colors"
              >
                <span class="text-muted-foreground text-xs w-5 flex-shrink-0">{{ q.sort_order }}.</span>
                <template v-if="editingQuestionId === q.id">
                  <input
                    v-model="editQuestionText"
                    class="bg-input border border-border rounded px-2 py-1 text-sm flex-1 min-w-0"
                    @keyup.enter="saveQuestion(form.id, q.id)"
                    @keyup.escape="editingQuestionId = null"
                  />
                  <button class="text-xs text-primary hover:text-primary/80 flex-shrink-0" @click="saveQuestion(form.id, q.id)">Save</button>
                  <button class="text-xs text-muted-foreground hover:text-foreground flex-shrink-0" @click="editingQuestionId = null">×</button>
                </template>
                <template v-else>
                  <span class="text-sm flex-1">{{ q.question_text }}</span>
                  <button
                    class="text-xs text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                    @click="editingQuestionId = q.id; editQuestionText = q.question_text"
                  >Edit</button>
                  <button
                    class="text-xs text-destructive hover:text-destructive/80 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                    @click="deleteQuestion(form.id, q.id)"
                  >✕</button>
                </template>
              </div>
            </div>
            <div class="flex gap-2 mt-2">
              <input
                v-model="newQuestionText[form.id]"
                placeholder="New question…"
                class="bg-input border border-border rounded px-3 py-1.5 text-sm flex-1 min-w-0"
                @keyup.enter="addQuestion(form.id)"
              />
              <button
                class="bg-muted hover:bg-muted/80 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-50"
                :disabled="!(newQuestionText[form.id] ?? '').trim()"
                @click="addQuestion(form.id)"
              >Add</button>
            </div>
          </div>

          <!-- Submissions link -->
          <div class="pt-1">
            <button
              class="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
              @click="router.replace({ query: { tab: 'application-submissions', formId: String(form.id) } })"
            >
              <Icon icon="mdi:file-account-outline" class="w-3.5 h-3.5" />
              View Submissions
              <Icon icon="mdi:arrow-right" class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
