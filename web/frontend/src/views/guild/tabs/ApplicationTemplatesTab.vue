<script setup lang="ts">
import { Icon } from "@iconify/vue";
import { onMounted, ref } from "vue";
import { api } from "@/api/client";
import type { ApplicationTemplateSchema } from "@/api/types";
import InfoTooltip from "@/components/InfoTooltip.vue";
import { useI18n } from "@/i18n";

const props = defineProps<{ guildId: string }>();

const { t } = useI18n();

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
    error.value = e instanceof Error ? e.message : t("common.load_failed");
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
        {
          name: templateDraft.value.name,
          approval_message: templateDraft.value.approval_message || null,
          denial_message: templateDraft.value.denial_message || null,
        },
      );
      const idx = templates.value.findIndex((t) => t.id === editingTemplateId.value);
      if (idx !== -1) templates.value[idx] = updated;
      editingTemplateId.value = null;
    } else {
      const created = await api.post<ApplicationTemplateSchema>(`/guilds/${props.guildId}/application-templates`, {
        name: templateDraft.value.name,
        approval_message: templateDraft.value.approval_message || null,
        denial_message: templateDraft.value.denial_message || null,
        question_texts: templateDraft.value.question_texts.filter((q) => q.trim()),
      });
      templates.value.push(created);
      showCreateTemplate.value = false;
    }
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  } finally {
    saving.value = false;
  }
}

async function deleteTemplate(templateId: number) {
  if (!confirm(t("tabs.application_templates.delete_confirm"))) return;
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-templates/${templateId}`);
    templates.value = templates.value.filter((t) => t.id !== templateId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}

async function addTemplateQuestion(templateId: number) {
  const text = (newTemplateQuestionText.value[templateId] ?? "").trim();
  if (!text) return;
  opError.value = null;
  try {
    const q = await api.post(`/guilds/${props.guildId}/application-templates/${templateId}/questions`, {
      question_text: text,
    });
    const tpl = templates.value.find((t) => t.id === templateId);
    if (tpl) tpl.questions.push(q as never);
    newTemplateQuestionText.value[templateId] = "";
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.save_failed");
  }
}

async function deleteTemplateQuestion(templateId: number, questionId: number) {
  opError.value = null;
  try {
    await api.delete(`/guilds/${props.guildId}/application-templates/${templateId}/questions/${questionId}`);
    const tpl = templates.value.find((t) => t.id === templateId);
    if (tpl) tpl.questions = tpl.questions.filter((q) => q.id !== questionId);
  } catch (e: unknown) {
    opError.value = e instanceof Error ? e.message : t("common.delete_failed");
  }
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h2 class="text-lg font-semibold">{{ t("tabs.application_templates.title") }}</h2>
        <p class="text-muted-foreground text-sm">{{ t("tabs.application_templates.desc") }}</p>
      </div>
      <button
        class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
        @click="showCreateTemplate = true; templateDraft = { name: '', approval_message: '', denial_message: '', question_texts: [''] }"
      >
        <Icon icon="mdi:plus" class="w-4 h-4" />
        {{ t("tabs.application_templates.new") }}
      </button>
    </div>

    <p v-if="opError" class="text-destructive text-sm">{{ opError }}</p>
    <div v-if="loading" class="text-muted-foreground text-sm">{{ t("common.loading") }}</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>

    <!-- Create Template Panel -->
    <div v-if="showCreateTemplate" class="bg-card border border-primary rounded p-4 space-y-3">
      <p class="text-sm font-semibold">{{ t("tabs.application_templates.new_panel") }}</p>
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium flex items-center gap-1.5">
          {{ t("tabs.application_templates.name_label") }}
          <InfoTooltip :text="t('tabs.application_templates.name_tooltip')" />
        </label>
        <input v-model="templateDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm w-64" />
      </div>
      <div class="space-y-1">
        <label class="text-sm font-medium flex items-center gap-1.5">
          {{ t("tabs.application_templates.questions_label") }}
          <InfoTooltip :text="t('tabs.application_templates.questions_tooltip')" />
        </label>
        <div v-for="(_, i) in templateDraft.question_texts" :key="i" class="flex gap-2">
          <input
            v-model="templateDraft.question_texts[i]"
            :placeholder="t('tabs.application_templates.question_placeholder', { num: i + 1 })"
            class="bg-input border border-border rounded px-3 py-1.5 text-sm flex-1"
          />
          <button class="text-destructive text-sm" @click="templateDraft.question_texts.splice(i, 1)">✕</button>
        </div>
        <button class="text-xs text-primary hover:text-primary/80 transition-colors" @click="templateDraft.question_texts.push('')">{{ t("tabs.application_templates.add_question") }}</button>
      </div>
      <div class="flex gap-2">
        <button
          class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
          :disabled="saving || !templateDraft.name.trim()"
          @click="saveTemplate"
        >{{ saving ? t("tabs.application_templates.saving") : t("common.create") }}</button>
        <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="showCreateTemplate = false">{{ t("common.cancel") }}</button>
      </div>
    </div>

    <!-- Template list -->
    <div v-if="!loading && !error" class="space-y-2">
      <p v-if="templates.length === 0" class="text-muted-foreground text-sm">{{ t("tabs.application_templates.empty") }}</p>

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
            <span class="text-xs text-muted-foreground">{{ tpl.questions.length === 1 ? t("tabs.application_templates.questions_count.one") : t("tabs.application_templates.questions_count.other", { count: tpl.questions.length }) }}</span>
            <span v-if="tpl.is_built_in" class="text-xs text-muted-foreground italic">{{ t("tabs.application_templates.built_in") }}</span>
          </button>
          <template v-if="!tpl.is_built_in">
            <button
              class="text-xs text-muted-foreground hover:text-foreground transition-colors"
              @click="editingTemplateId = tpl.id; templateDraft = { name: tpl.name, approval_message: tpl.approval_message ?? '', denial_message: tpl.denial_message ?? '', question_texts: [] }; expandedTemplateId = tpl.id"
            >{{ t("common.edit") }}</button>
            <button class="text-xs text-destructive hover:text-destructive/80 transition-colors" @click="deleteTemplate(tpl.id)">{{ t("common.delete") }}</button>
          </template>
        </div>

        <div v-if="expandedTemplateId === tpl.id" class="border-t border-border px-4 py-3 space-y-3">
          <!-- Inline edit -->
          <div v-if="editingTemplateId === tpl.id && !tpl.is_built_in" class="space-y-2 pb-3 border-b border-border">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium flex items-center gap-1.5">
                {{ t("tabs.application_templates.name_label") }}
                <InfoTooltip :text="t('tabs.application_templates.name_tooltip')" />
              </label>
              <input v-model="templateDraft.name" class="bg-input border border-border rounded px-3 py-2 text-sm w-64" />
            </div>
            <div class="flex gap-2">
              <button
                class="bg-primary hover:bg-primary/90 text-primary-foreground px-3 py-1.5 rounded text-sm font-medium disabled:opacity-50 transition-colors"
                :disabled="saving"
                @click="saveTemplate"
              >{{ saving ? t("tabs.application_templates.saving") : t("common.save") }}</button>
              <button class="text-muted-foreground hover:text-foreground text-sm transition-colors" @click="editingTemplateId = null">{{ t("common.cancel") }}</button>
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
              :placeholder="t('tabs.application_templates.new_question_placeholder')"
              class="bg-input border border-border rounded px-3 py-1.5 text-sm flex-1"
              @keyup.enter="addTemplateQuestion(tpl.id)"
            />
            <button
              class="bg-muted hover:bg-muted/80 px-3 py-1.5 rounded text-sm transition-colors disabled:opacity-50"
              :disabled="!(newTemplateQuestionText[tpl.id] ?? '').trim()"
              @click="addTemplateQuestion(tpl.id)"
            >{{ t("common.add") }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
