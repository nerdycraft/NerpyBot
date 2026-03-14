<script setup lang="ts">
import { computed } from "vue";
import { useMockup, type MockupLevel } from "@/composables/useMockup";
import { useAuthStore } from "@/stores/auth";
import { useI18n, type I18nKey } from "@/i18n";

const auth = useAuthStore();
const { mockupLevel, setMockupLevel, clearMockup } = useMockup();
const { t } = useI18n();

const levels: { value: MockupLevel; labelKey: I18nKey }[] = [
  { value: "admin", labelKey: "mockup.levels.admin" },
  { value: "mod", labelKey: "mockup.levels.mod" },
  { value: "member", labelKey: "mockup.levels.member" },
];

const mockupLevelLabel = computed(() => {
  const level = levels.find((l) => l.value === mockupLevel.value);
  return level ? t(level.labelKey) : (mockupLevel.value ?? "");
});

function onSelect(e: Event) {
  const val = (e.target as HTMLSelectElement).value as MockupLevel;
  if (val) {
    setMockupLevel(val);
  } else {
    clearMockup();
  }
}
</script>

<template>
  <div v-if="auth.user?.is_operator">
    <!-- Active mockup banner -->
    <div
      v-if="mockupLevel"
      class="mb-4 flex items-center justify-between gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded px-4 py-2.5 text-yellow-400 text-sm"
    >
      <span>
        <strong>{{ t("mockup.title") }}</strong> — {{ t("mockup.simulating") }}
        <strong>{{ mockupLevelLabel }}</strong>. {{ t("mockup.sections_hidden") }}
      </span>
      <button
        class="text-xs underline hover:no-underline flex-shrink-0"
        @click="clearMockup"
      >
        {{ t("mockup.exit") }}
      </button>
    </div>

    <!-- Inactive — subtle dropdown -->
    <div v-else class="mb-4 flex items-center gap-2 text-xs text-muted-foreground/60">
      <span id="mockup-simulate-as">{{ t("mockup.simulate_as") }}</span>
      <select
        class="bg-transparent border border-border rounded px-2 py-0.5 text-xs text-muted-foreground cursor-pointer hover:border-primary transition-colors"
        aria-labelledby="mockup-simulate-as"
        @change="onSelect"
      >
        <option value="">{{ t("mockup.choose_level") }}</option>
        <option v-for="l in levels" :key="l.value!" :value="l.value!">{{ t(l.labelKey) }}</option>
      </select>
    </div>
  </div>
</template>
