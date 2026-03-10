<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Icon } from "@iconify/vue";
import { api } from "@/api/client";
import type { ApplicationTemplateSchema } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";

const props = defineProps<{ guildId: string }>();

const templates = ref<ApplicationTemplateSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const showCreateTemplate = ref(false);
const editingTemplateId = ref<number | null>(null);
const expandedTemplateId = ref<number | null>(null);
const newTemplateQuestionText = ref<Record<number, string>>({});

const saving = ref(false);
const opError = ref<string | null>(null);
const templateDraft = ref({ name: "", approval_message: "", denial_message: "", question_texts: [""] });

onMounted(load);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    templates.value = await api.get<ApplicationTemplateSchema[]>(`/guilds/${props.guildId}/application-templates`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
}

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
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">Templates</h2>
        <p class="text-muted-foreground text-sm">Templates are reusable question sets that can be shared across multiple application forms, letting you define common question banks once and apply them wherever needed. Built-in templates are provided by the bot and cannot be modified or deleted.</p>
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
        @click="showCreateTemplate = true; templateDraft = { name: '', approval_message: '', denial_message: '', question_texts: [''] }"
      >
        <Icon icon="mdi:plus" class="w-4 h-4" />
        New Template
      </button>
    </div>

    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <!-- Create Template Panel -->
    <div v-if="showCreateTemplate" class="bg-card border border-primary rounded p-4 space-y-3">
      <p class="text-sm font-semibold">New Template</p>
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium flex items-center gap-1.5">
          Name
          <InfoTooltip text="A unique name identifying this template. Used when selecting a template to base a new form on." />
        </label>
        <input v-model="templateDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm w-64" />
      </div>
      <div class="space-y-1">
        <label class="text-sm font-medium flex items-center gap-1.5">
          Questions
          <InfoTooltip text="The questions members will be asked when filling out a form that uses this template. Questions are presented in order via DM." />
        </label>
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
    <div v-if="!loading && !error" class="space-y-2">
      <p v-if="templates.length === 0" class="text-muted-foreground text-sm">No templates.</p>

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
            <button
              class="text-xs text-muted-foreground hover:text-foreground transition-colors"
              @click="editingTemplateId = tpl.id; templateDraft = { name: tpl.name, approval_message: tpl.approval_message ?? '', denial_message: tpl.denial_message ?? '', question_texts: [] }; expandedTemplateId = tpl.id"
            >Edit</button>
            <button class="text-xs text-destructive hover:text-destructive/80 transition-colors" @click="deleteTemplate(tpl.id)">Delete</button>
          </template>
        </div>

        <div v-if="expandedTemplateId === tpl.id" class="border-t border-border px-4 py-3 space-y-3">
          <!-- Inline edit -->
          <div v-if="editingTemplateId === tpl.id && !tpl.is_built_in" class="space-y-2 pb-3 border-b border-border">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium flex items-center gap-1.5">
                Name
                <InfoTooltip text="A unique name identifying this template. Used when selecting a template to base a new form on." />
              </label>
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
</template>
