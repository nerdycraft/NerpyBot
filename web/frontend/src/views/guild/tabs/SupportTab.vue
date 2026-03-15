<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/api/client";
import type { SupportMessageRequest, SupportMessageResponse } from "@/api/types";
import { type I18nKey, useI18n } from "@/i18n";

type Category = SupportMessageRequest["category"];

const { t } = useI18n();

const CATEGORIES: { value: Category; labelKey: I18nKey }[] = [
  { value: "bug", labelKey: "tabs.support.category.bug" },
  { value: "feature", labelKey: "tabs.support.category.feature" },
  { value: "feedback", labelKey: "tabs.support.category.feedback" },
  { value: "other", labelKey: "tabs.support.category.other" },
];

const category = ref<Category>("feedback");
const message = ref("");
const submitting = ref(false);
const error = ref<string | null>(null);
const successCount = ref<number | null>(null);

async function submit() {
  error.value = null;
  successCount.value = null;
  submitting.value = true;
  try {
    const result = await api.post<SupportMessageResponse>("/support/message", {
      category: category.value,
      message: message.value,
    } satisfies SupportMessageRequest);
    successCount.value = result.sent_to;
    message.value = "";
    category.value = "feedback";
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : t("tabs.support.send_failed");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">{{ t("tabs.support.title") }}</h2>
      <p class="text-muted-foreground text-sm">{{ t("tabs.support.desc") }}</p>
    </div>

    <div v-if="successCount !== null" class="rounded-md bg-green-900/30 border border-green-700 px-4 py-3 text-sm text-green-300">
      {{ t(successCount === 1 ? "tabs.support.success_one" : "tabs.support.success_many", { count: successCount }) }}
      <button class="ml-2 underline hover:no-underline" @click="successCount = null">
        {{ t("tabs.support.send_another") }}
      </button>
    </div>

    <form v-else class="space-y-4" @submit.prevent="submit">
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="support-category">{{ t("tabs.support.category_label") }}</label>
        <select
          id="support-category"
          v-model="category"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-56"
        >
          <option v-for="c in CATEGORIES" :key="c.value" :value="c.value">{{ t(c.labelKey) }}</option>
        </select>
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="support-message">
          {{ t("tabs.support.message_label") }}
          <span class="text-muted-foreground font-normal">{{ t("tabs.support.message_hint") }}</span>
        </label>
        <textarea
          id="support-message"
          v-model="message"
          rows="6"
          maxlength="2000"
          :placeholder="t('tabs.support.placeholder')"
          class="bg-input border border-border rounded px-3 py-2 text-sm resize-y"
          required
          minlength="10"
        />
        <span class="text-xs text-muted-foreground self-end">
          {{ t("tabs.support.char_count", { count: message.length }) }}
        </span>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>

      <button
        type="submit"
        :disabled="submitting || message.length < 10"
        class="bg-primary text-primary-foreground rounded px-4 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {{ submitting ? t("tabs.support.submitting") : t("tabs.support.submit") }}
      </button>
    </form>
  </div>
</template>
