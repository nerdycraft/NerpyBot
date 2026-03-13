<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/api/client";
import type { SupportMessageRequest, SupportMessageResponse } from "@/api/types";

type Category = SupportMessageRequest["category"];

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "bug", label: "Bug Report" },
  { value: "feature", label: "Feature Request" },
  { value: "feedback", label: "Feedback" },
  { value: "other", label: "Other" },
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
    error.value = e instanceof Error ? e.message : "Failed to send message";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Contact & Feedback</h2>
      <p class="text-muted-foreground text-sm">
        Send a bug report, feature request, or general feedback to the bot operators. Messages are delivered directly
        via Discord DM.
      </p>
    </div>

    <div v-if="successCount !== null" class="rounded-md bg-green-900/30 border border-green-700 px-4 py-3 text-sm text-green-300">
      Message sent successfully to {{ successCount }} operator{{ successCount === 1 ? "" : "s" }}.
      <button class="ml-2 underline hover:no-underline" @click="successCount = null">Send another</button>
    </div>

    <form v-else class="space-y-4" @submit.prevent="submit">
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="support-category">Category</label>
        <select
          id="support-category"
          v-model="category"
          class="bg-input border border-border rounded px-3 py-2 text-sm w-56"
        >
          <option v-for="c in CATEGORIES" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
      </div>

      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium" for="support-message">
          Message
          <span class="text-muted-foreground font-normal">(10–2000 characters)</span>
        </label>
        <textarea
          id="support-message"
          v-model="message"
          rows="6"
          maxlength="2000"
          placeholder="Describe your issue or idea…"
          class="bg-input border border-border rounded px-3 py-2 text-sm resize-y"
          required
          minlength="10"
        />
        <span class="text-xs text-muted-foreground self-end">{{ message.length }} / 2000</span>
      </div>

      <p v-if="error" class="text-destructive text-sm">{{ error }}</p>

      <button
        type="submit"
        :disabled="submitting || message.length < 10"
        class="bg-primary text-primary-foreground rounded px-4 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {{ submitting ? "Sending…" : "Send Message" }}
      </button>
    </form>
  </div>
</template>
