<script setup lang="ts">
import LegalPageLayout from "@/components/LegalPageLayout.vue";
import { useLegalContact } from "@/composables/useLegalContact";
import { useI18n } from "@/i18n";

const { t, locale } = useI18n();
const { contact } = useLegalContact();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.impressum')"
    :back-text="t('legal.back')"
    :show-meta="false"
    :footer-links="[{ to: '/terms', text: t('legal.terms') }, { to: '/privacy', text: t('legal.privacy') }]"
  >
    <template v-if="contact.enabled">
      <section>
        <h2>{{ t('legal.impressum_page.legal_info_title') }}</h2>
        <p>
          {{ contact.name }}<br>
          {{ contact.street }}<br>
          {{ contact.zip_city }}<br>
          {{ locale.current === 'de' ? contact.country_de : contact.country_en }}
        </p>
      </section>

      <section>
        <h2>{{ t('legal.impressum_page.contact_title') }}</h2>
        <p>{{ t('legal.impressum_page.contact_email_prefix') }}{{ contact.email }}</p>
      </section>

      <section>
        <h2>{{ t('legal.impressum_page.responsible_title') }}</h2>
        <p>
          {{ contact.name }}<br>
          {{ contact.street }}<br>
          {{ contact.zip_city }}
        </p>
      </section>
    </template>

    <section>
      <h2>{{ t('legal.impressum_page.disclaimer_title') }}</h2>
      <p>{{ t('legal.impressum_page.disclaimer_body') }}</p>
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
</style>
