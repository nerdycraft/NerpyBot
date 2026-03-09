<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type {
  ApplicationFormSchema,
  ApplicationSubmissionSchema,
  ApplicationTemplateSchema,
} from "@/api/types";
import DiscordPicker from "@/components/DiscordPicker.vue";

const props = defineProps<{ guildId: string }>();

// ── State ──
const forms = ref<ApplicationFormSchema[]>([]);
const templates = ref<ApplicationTemplateSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const expandedFormId = ref<number | null>(null);
const editingFormId = ref<number | null>(null);
const showCreateForm = ref(false);

const submissions = ref<Record<number, ApplicationSubmissionSchema[]>>({});
const submissionsLoading = ref<Record<number, boolean>>({});
const expandedSubmissionsFormId = ref<number | null>(null);

const editingQuestionId = ref<number | null>(null);
const editQuestionText = ref("");
const newQuestionText = ref<Record<number, string>>({});

const showCreateTemplate = ref(false);
const editingTemplateId = ref<number | null>(null);
const expandedTemplateId = ref<number | null>(null);
const newTemplateQuestionText = ref<Record<number, string>>({});

const saving = ref(false);
const opError = ref<string | null>(null);
const questionSavedFormId = ref<number | null>(null);

function flashQuestionSaved(formId: number) {
  questionSavedFormId.value = formId;
  setTimeout(() => { questionSavedFormId.value = null; }, 1800);
}

// Blank form state
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
const templateDraft = ref({ name: "", approval_message: "", denial_message: "", question_texts: [""] });

// ── Load ──
onMounted(load);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    [forms.value, templates.value] = await Promise.all([
      api.get<ApplicationFormSchema[]>(`/guilds/${props.guildId}/application-forms`),
      api.get<ApplicationTemplateSchema[]>(`/guilds/${props.guildId}/application-templates`),
    ]);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

// ── Forms ──
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

// ── Questions ──
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

// ── Submissions ──
async function loadSubmissions(formId: number) {
  if (expandedSubmissionsFormId.value === formId) {
    expandedSubmissionsFormId.value = null;
    return;
  }
  expandedSubmissionsFormId.value = formId;
  if (submissions.value[formId]) return;
  submissionsLoading.value[formId] = true;
  try {
    submissions.value[formId] = await api.get<ApplicationSubmissionSchema[]>(
      `/guilds/${props.guildId}/application-forms/${formId}/submissions`,
    );
  } finally {
    submissionsLoading.value[formId] = false;
  }
}

const statusColor: Record<string, string> = {
  pending: "text-yellow-400",
  approved: "text-green-400",
  denied: "text-destructive",
};

// ── Templates ──

async function saveTemplate() {
  saving.value = true;
  opError.value = null;
  try {
    if (editingTemplateId.value !== null) {
      const updated = await api.put<ApplicationTemplateSchema>(
        `/guilds/${props.guildId}/application-templates/${editingTemplateId.value}`,
        { name: templateDraft.value.name, approval_message: templateDraft.value.approval_message || null, denial_message: templateDraft.value.denial_message || null },
      );
      const idx = templates.value.findIndex((t) => t.id === editingTemplateId.value);
      if (idx !== -1) templates.value[idx] = updated;
      editingTemplateId.value = null;
    } else {
      const created = await api.post<ApplicationTemplateSchema>(
        `/guilds/${props.guildId}/application-templates`,
        {
          name: templateDraft.value.name,
          approval_message: templateDraft.value.approval_message || null,
          denial_message: templateDraft.value.denial_message || null,
          question_texts: templateDraft.value.question_texts.filter((q) => q.trim()),
        },
      );
      templates.value.push(created);
      showCreateTemplate.value = false;
    }
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Save failed";
  } finally {
    saving.value = false;
  }
}

async function deleteTemplate(templateId: number) {
  if (!confirm("Delete this template?")) return;
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-templates/${templateId}`);
    templates.value = templates.value.filter((t) => t.id !== templateId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Delete failed";
  }
}

async function addTemplateQuestion(templateId: number) {
  const text = (newTemplateQuestionText.value[templateId] ?? "").trim();
  if (!text) return;
  opError.value = null;
  try {
    const q = await api.post(`/guilds/${props.guildId}/application-templates/${templateId}/questions`, { question_text: text });
    const tpl = templates.value.find((t) => t.id === templateId);
    if (tpl) tpl.questions.push(q as never);
    newTemplateQuestionText.value[templateId] = "";
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to add question";
  }
}

async function deleteTemplateQuestion(templateId: number, questionId: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-templates/${templateId}/questions/${questionId}`);
    const tpl = templates.value.find((t) => t.id === templateId);
    if (tpl) tpl.questions = tpl.questions.filter((q) => q.id !== questionId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : "Failed to delete question";
  }
}
</script>

<template>
  <div class="space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-semibold">Application Forms</h2>
        <p class="text-muted-foreground text-sm">Manage application forms, questions, and templates.</p>
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5"
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
          <label class="text-xs text-muted-foreground">Name</label>
          <input v-model="formDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm" placeholder="e.g. Guild Application" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Review Channel <span class="text-muted-foreground/60">(where votes appear)</span></label>
          <DiscordPicker v-model="formDraft.review_channel_id" :guild-id="guildId" kind="channel" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Apply Channel <span class="text-muted-foreground/60">(where the Apply button is posted)</span></label>
          <DiscordPicker v-model="formDraft.apply_channel_id" :guild-id="guildId" kind="channel" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-xs text-muted-foreground">Apply description <span class="text-muted-foreground/60">(shown on the Apply button embed, optional)</span></label>
          <textarea v-model="formDraft.apply_description" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Required Approvals</label>
          <input v-model.number="formDraft.required_approvals" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Required Denials</label>
          <input v-model.number="formDraft.required_denials" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-xs text-muted-foreground">Approval message (optional)</label>
          <textarea v-model="formDraft.approval_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
        </div>
        <div class="flex flex-col gap-1 sm:col-span-2">
          <label class="text-xs text-muted-foreground">Denial message (optional)</label>
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
        <!-- Form header row -->
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

        <!-- Expanded content -->
        <div v-if="expandedFormId === form.id" class="border-t border-border px-4 py-4 space-y-5">

          <!-- Inline edit panel -->
          <div v-if="editingFormId === form.id" class="space-y-3 pb-3 border-b border-border">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Edit Settings</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Name</label>
                <input v-model="formDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Review Channel <span class="text-muted-foreground/60">(where votes appear)</span></label>
                <DiscordPicker v-model="formDraft.review_channel_id" :guild-id="guildId" kind="channel" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Apply Channel <span class="text-muted-foreground/60">(where Apply button is posted)</span></label>
                <DiscordPicker v-model="formDraft.apply_channel_id" :guild-id="guildId" kind="channel" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-xs text-muted-foreground">Apply description <span class="text-muted-foreground/60">(shown on the Apply embed, optional)</span></label>
                <textarea v-model="formDraft.apply_description" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Required Approvals</label>
                <input v-model.number="formDraft.required_approvals" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Required Denials</label>
                <input v-model.number="formDraft.required_denials" type="number" min="1" class="bg-input border border-border rounded px-3 py-2 text-sm w-24" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-xs text-muted-foreground">Approval message (optional)</label>
                <textarea v-model="formDraft.approval_message" rows="2" class="bg-input border border-border rounded px-3 py-2 text-sm resize-y" />
              </div>
              <div class="flex flex-col gap-1 sm:col-span-2">
                <label class="text-xs text-muted-foreground">Denial message (optional)</label>
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
            <span v-if="form.review_channel_id">Review channel: {{ form.review_channel_id }}</span>
            <span v-if="form.apply_channel_id">Apply channel: {{ form.apply_channel_id }}</span>
            <span v-if="form.approval_message">Approval message set</span>
            <span v-if="form.denial_message">Denial message set</span>
          </div>

          <!-- Questions -->
          <div class="space-y-2">
            <div class="flex items-center gap-2">
              <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Questions</p>
              <span
                v-if="questionSavedFormId === form.id"
                class="text-xs text-green-400 transition-opacity"
              >✓ Saved</span>
            </div>
            <p v-if="form.questions.length === 0" class="text-muted-foreground text-xs">No questions yet.</p>
            <div
              v-for="q in [...form.questions].sort((a, b) => a.sort_order - b.sort_order)"
              :key="q.id"
              class="flex items-start gap-2 group"
            >
              <span class="text-muted-foreground text-xs w-5 flex-shrink-0 pt-0.5">{{ q.sort_order }}.</span>
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
            <!-- Add question -->
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

          <!-- Submissions -->
          <div class="space-y-2">
            <button
              class="text-xs font-semibold text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors flex items-center gap-1"
              @click="loadSubmissions(form.id)"
            >
              <Icon :icon="expandedSubmissionsFormId === form.id ? 'mdi:chevron-down' : 'mdi:chevron-right'" class="w-3.5 h-3.5" />
              Submissions
            </button>
            <div v-if="expandedSubmissionsFormId === form.id">
              <div v-if="submissionsLoading[form.id]" class="text-muted-foreground text-xs">Loading…</div>
              <p v-else-if="!submissions[form.id]?.length" class="text-muted-foreground text-xs">No submissions.</p>
              <div v-else class="space-y-2">
                <div
                  v-for="sub in submissions[form.id]"
                  :key="sub.id"
                  class="bg-background border border-border rounded px-3 py-2 space-y-1"
                >
                  <div class="flex items-center justify-between">
                    <span class="text-sm font-medium">{{ sub.user_name ?? sub.user_id }}</span>
                    <span :class="['text-xs capitalize', statusColor[sub.status] ?? 'text-muted-foreground']">{{ sub.status }}</span>
                  </div>
                  <p class="text-xs text-muted-foreground">{{ sub.submitted_at }}</p>
                  <div class="space-y-1 pt-1">
                    <div v-for="a in sub.answers" :key="a.question_id" class="text-xs">
                      <span class="text-muted-foreground">{{ a.question_text }}</span>
                      <p class="text-foreground/80 pl-2">{{ a.answer_text }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Templates ── -->
    <div class="space-y-4 pt-4 border-t border-border">
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-base font-semibold">Templates</h3>
          <p class="text-muted-foreground text-xs">Reusable question sets. Built-in templates are read-only.</p>
        </div>
        <button
          class="bg-muted hover:bg-muted/80 px-3 py-1.5 rounded text-sm transition-colors flex items-center gap-1.5"
          @click="showCreateTemplate = true; templateDraft = { name: '', approval_message: '', denial_message: '', question_texts: [''] }"
        >
          <Icon icon="mdi:plus" class="w-4 h-4" />
          New Template
        </button>
      </div>

      <!-- Create Template Panel -->
      <div v-if="showCreateTemplate" class="bg-card border border-primary rounded p-4 space-y-3">
        <p class="text-sm font-semibold">New Template</p>
        <div class="flex flex-col gap-1">
          <label class="text-xs text-muted-foreground">Name</label>
          <input v-model="templateDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm w-64" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-muted-foreground">Questions</label>
          <div v-for="(_, i) in templateDraft.question_texts" :key="i" class="flex gap-2">
            <input
              v-model="templateDraft.question_texts[i]"
              :placeholder="`Question ${i + 1}…`"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm flex-1"
            />
            <button class="text-destructive text-sm" @click="templateDraft.question_texts.splice(i, 1)">✕</button>
          </div>
          <button class="text-xs text-primary hover:text-primary/80 transition-colors" @click="templateDraft.question_texts.push('')">+ Add question</button>
        </div>
        <div class="flex gap-2">
          <button
            class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
            :disabled="saving || !templateDraft.name.trim()"
            @click="saveTemplate"
          >{{ saving ? "Saving…" : "Create" }}</button>
          <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="showCreateTemplate = false">Cancel</button>
        </div>
      </div>

      <!-- Template list -->
      <div v-if="!loading" class="space-y-2">
        <p v-if="templates.length === 0" class="text-muted-foreground text-xs">No templates.</p>

        <div
          v-for="tpl in templates"
          :key="tpl.id"
          class="bg-card border border-border rounded overflow-hidden"
          :class="{ 'opacity-60': tpl.is_built_in }"
        >
          <div class="flex items-center gap-3 px-4 py-2.5">
            <button class="flex-1 flex items-center gap-2 text-left" @click="expandedTemplateId = expandedTemplateId === tpl.id ? null : tpl.id">
              <Icon :icon="expandedTemplateId === tpl.id ? 'mdi:chevron-down' : 'mdi:chevron-right'" class="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <span class="text-sm font-medium">{{ tpl.name }}</span>
              <span class="text-xs text-muted-foreground">{{ tpl.questions.length }} questions</span>
              <span v-if="tpl.is_built_in" class="text-xs text-muted-foreground italic">built-in</span>
            </button>
            <template v-if="!tpl.is_built_in">
              <button class="text-xs text-muted-foreground hover:text-foreground transition-colors"
                @click="editingTemplateId = tpl.id; templateDraft = { name: tpl.name, approval_message: tpl.approval_message ?? '', denial_message: tpl.denial_message ?? '', question_texts: [] }; expandedTemplateId = tpl.id"
              >Edit</button>
              <button class="text-xs text-destructive hover:text-destructive/80 transition-colors" @click="deleteTemplate(tpl.id)">Delete</button>
            </template>
          </div>

          <div v-if="expandedTemplateId === tpl.id" class="border-t border-border px-4 py-3 space-y-3">
            <!-- Inline edit for guild template -->
            <div v-if="editingTemplateId === tpl.id && !tpl.is_built_in" class="space-y-2 pb-3 border-b border-border">
              <div class="flex flex-col gap-1">
                <label class="text-xs text-muted-foreground">Name</label>
                <input v-model="templateDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm w-64" />
              </div>
              <div class="flex gap-2">
                <button
                  class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
                  :disabled="saving"
                  @click="saveTemplate"
                >{{ saving ? "Saving…" : "Save" }}</button>
                <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="editingTemplateId = null">Cancel</button>
              </div>
            </div>

            <!-- Questions list -->
            <ol class="space-y-1">
              <li
                v-for="q in [...tpl.questions].sort((a, b) => a.sort_order - b.sort_order)"
                :key="q.id"
                class="flex items-start gap-2 group text-sm"
              >
                <span class="text-muted-foreground text-xs w-5 flex-shrink-0 pt-0.5">{{ q.sort_order }}.</span>
                <span class="flex-1">{{ q.question_text }}</span>
                <button
                  v-if="!tpl.is_built_in"
                  class="text-xs text-destructive hover:text-destructive/80 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                  @click="deleteTemplateQuestion(tpl.id, q.id)"
                >✕</button>
              </li>
            </ol>
            <!-- Add question (guild templates only) -->
            <div v-if="!tpl.is_built_in" class="flex gap-2">
              <input
                v-model="newTemplateQuestionText[tpl.id]"
                placeholder="New question…"
                class="bg-input border border-border rounded px-3 py-1.5 text-sm flex-1"
                @keyup.enter="addTemplateQuestion(tpl.id)"
              />
              <button
                class="bg-muted hover:bg-muted/80 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-50"
                :disabled="!(newTemplateQuestionText[tpl.id] ?? '').trim()"
                @click="addTemplateQuestion(tpl.id)"
              >Add</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
