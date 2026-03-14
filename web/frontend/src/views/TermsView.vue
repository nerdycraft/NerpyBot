<script setup lang="ts">
import { useI18n } from "@/i18n";
import LegalPageLayout from "@/components/LegalPageLayout.vue";

const { t } = useI18n();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.terms')"
    :back-text="t('legal.back')"
    :footer-links="[{ to: '/privacy', text: t('legal.privacy') }, { to: '/impressum', text: t('legal.impressum') }]"
  >
    <section>
      <h2>{{ t('legal.terms_page.acceptance_title') }}</h2>
      <p>{{ t('legal.terms_page.acceptance_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.description_title') }}</h2>
      <p>{{ t('legal.terms_page.description_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.acceptable_use_title') }}</h2>
      <p>{{ t('legal.terms_page.acceptable_use_intro') }}</p>
      <ul>
        <li>{{ t('legal.terms_page.acceptable_use_item_discord') }}</li>
        <li>{{ t('legal.terms_page.acceptable_use_item_harass') }}</li>
        <li>{{ t('legal.terms_page.acceptable_use_item_exploit') }}</li>
        <li>{{ t('legal.terms_page.acceptable_use_item_unlawful') }}</li>
      </ul>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.access_title') }}</h2>
      <p>{{ t('legal.terms_page.access_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.warranty_title') }}</h2>
      <p>{{ t('legal.terms_page.warranty_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.liability_title') }}</h2>
      <p>{{ t('legal.terms_page.liability_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.changes_title') }}</h2>
      <p>{{ t('legal.terms_page.changes_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.contact_title') }}</h2>
      <p>
        {{ t('legal.terms_page.contact_body_before') }}<RouterLink to="/impressum" class="inline-link">{{ t('legal.terms_page.contact_body_link') }}</RouterLink>{{ t('legal.terms_page.contact_body_after') }}
      </p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.governing_law_title') }}</h2>
      <p>{{ t('legal.terms_page.governing_law_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.terms_page.dispute_title') }}</h2>
      <p>
        {{ t('legal.terms_page.dispute_body_before') }}<a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer" class="inline-link">https://ec.europa.eu/consumers/odr</a>{{ t('legal.terms_page.dispute_body_after') }}
      </p>
    </section>
  </LegalPageLayout>
</template>

<style scoped>
section { display: flex; flex-direction: column; gap: 0.5rem; }

h2 {
  font-family: 'Syne', sans-serif;
  font-size: 1rem;
  font-weight: 700;
  color: hsl(210, 40%, 92%);
  margin: 0;
}

p { margin: 0; }

ul {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

li { color: hsl(210, 40%, 78%); }

.inline-link {
  color: hsl(224, 76%, 70%);
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: color 0.15s;
}
.inline-link:hover { color: hsl(224, 100%, 82%); }
</style>
