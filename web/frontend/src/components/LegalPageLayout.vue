<script setup lang="ts">
import { RouterLink } from "vue-router";
import { Icon } from "@iconify/vue";
import { useI18n } from "@/i18n";
import LanguageSwitcher from "@/components/LanguageSwitcher.vue";

withDefaults(defineProps<{
  title: string;
  backText: string;
  footerLinks: Array<{ to: string; text: string }>;
  showMeta?: boolean;
}>(), {
  showMeta: true,
});

const { t } = useI18n();
</script>

<template>
  <div class="legal-bg" aria-hidden="true" />

  <div class="min-h-screen relative z-10 px-4 py-12">
    <div class="legal-card">
      <div class="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>

      <RouterLink to="/login" class="back-link">
        <Icon icon="mdi:arrow-left" class="w-4 h-4" />
        {{ backText }}
      </RouterLink>

      <h1 class="legal-title">{{ title }}</h1>
      <p v-if="showMeta" class="legal-meta">{{ t("legal.last_updated") }}</p>

      <slot />

      <div class="legal-footer">
        <RouterLink
          v-for="link in footerLinks"
          :key="link.to"
          :to="link.to"
          class="legal-link"
        >{{ link.text }}</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.legal-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: hsl(222, 47%, 8%);
}

.legal-card {
  position: relative;
  max-width: 720px;
  margin: 0 auto;
  background: rgba(10, 14, 28, 0.72);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  padding: 2.5rem;
  box-shadow: 0 32px 64px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(88, 101, 242, 0.12);
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  color: hsl(210, 40%, 85%);
  font-family: 'Figtree', sans-serif;
  font-size: 0.9375rem;
  line-height: 1.7;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  color: hsl(215, 20%, 55%);
  text-decoration: none;
  transition: color 0.15s;
}
.back-link:hover { color: hsl(210, 40%, 85%); }

.legal-title {
  font-family: 'Syne', sans-serif;
  font-size: 1.75rem;
  font-weight: 800;
  background: linear-gradient(135deg, #ffffff 0%, hsl(224, 100%, 82%) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin: 0;
}

.legal-meta {
  font-size: 0.8125rem;
  color: hsl(215, 20%, 45%);
  margin: -1rem 0 0;
}

.legal-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 1rem;
  display: flex;
  gap: 1rem;
}

.legal-link {
  font-size: 0.875rem;
  color: hsl(215, 20%, 55%);
  text-decoration: none;
  transition: color 0.15s;
}
.legal-link:hover { color: hsl(210, 40%, 85%); }
</style>
