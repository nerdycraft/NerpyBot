<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@/api/client";
import type { ApplicationFormSchema } from "@/api/types";

const props = defineProps<{ guildId: string }>();

const forms = ref<ApplicationFormSchema[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    forms.value = await api.get<ApplicationFormSchema[]>(`/guilds/${props.guildId}/application-forms`);
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-lg font-semibold">Application Forms</h2>
      <p class="text-muted-foreground text-sm">Custom application forms configured for this server (read-only).</p>
    </div>

    <div v-if="loading" class="text-muted-foreground text-sm">Loading…</div>
    <p v-else-if="error" class="text-destructive text-sm">{{ error }}</p>
    <p v-else-if="forms.length === 0" class="text-muted-foreground text-sm">No application forms configured.</p>

    <div v-else class="space-y-4">
      <div
        v-for="form in forms"
        :key="form.id"
        class="bg-card border border-border rounded p-4 space-y-3"
      >
        <div class="flex items-start justify-between gap-4">
          <span class="font-semibold text-sm">{{ form.name }}</span>
          <div class="text-xs text-muted-foreground flex gap-3 flex-shrink-0">
            <span>✓ {{ form.required_approvals }} approvals</span>
            <span>✗ {{ form.required_denials }} denials</span>
          </div>
        </div>

        <div v-if="form.questions.length > 0" class="space-y-1">
          <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Questions</p>
          <ol class="space-y-1">
            <li
              v-for="q in [...form.questions].sort((a, b) => a.sort_order - b.sort_order)"
              :key="q.id"
              class="text-sm text-foreground/80 flex gap-2"
            >
              <span class="text-muted-foreground flex-shrink-0">{{ q.sort_order }}.</span>
              <span>{{ q.question_text }}</span>
            </li>
          </ol>
        </div>
        <p v-else class="text-muted-foreground text-xs">No questions defined.</p>
      </div>
    </div>
  </div>
</template>
