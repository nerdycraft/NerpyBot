<script setup lang="ts">
import LegalPageLayout from "@/components/LegalPageLayout.vue";
import { useLegalContact } from "@/composables/useLegalContact";
import { useI18n } from "@/i18n";

const { t, locale } = useI18n();
const { contact } = useLegalContact();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.privacy')"
    :back-text="t('legal.back')"
    :footer-links="[{ to: '/terms', text: t('legal.terms') }, { to: '/impressum', text: t('legal.impressum') }]"
  >
    <div v-if="contact.enabled" class="controller-block">
      <p class="controller-label">{{ t('legal.privacy_page.controller_label') }}</p>
      <p>
        {{ contact.name }}<br>
        {{ contact.street }}<br>
        {{ contact.zip_city }}, {{ locale.current === 'de' ? contact.country_de : contact.country_en }}<br>
        {{ t('legal.impressum_page.contact_email_prefix') }}{{ contact.email }}
      </p>
    </div>

    <section>
      <h2>{{ t('legal.privacy_page.data_collection_title') }}</h2>
      <p>{{ t('legal.privacy_page.data_collection_intro') }}</p>
      <ul>
        <li v-html="t('legal.privacy_page.data_collection_item_guild_ids')" />
        <li v-html="t('legal.privacy_page.data_collection_item_user_ids')" />
        <li v-html="t('legal.privacy_page.data_collection_item_channel_role_ids')" />
        <li v-html="t('legal.privacy_page.data_collection_item_application')" />
        <li v-html="t('legal.privacy_page.data_collection_item_config')" />
      </ul>
      <p>{{ t('legal.privacy_page.data_collection_outro') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.data_use_title') }}</h2>
      <p>{{ t('legal.privacy_page.data_use_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.data_retention_title') }}</h2>
      <p>{{ t('legal.privacy_page.data_retention_body1') }}</p>
      <p>{{ t('legal.privacy_page.data_retention_body2') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.data_sharing_title') }}</h2>
      <p>{{ t('legal.privacy_page.data_sharing_body1') }}</p>
      <p>{{ t('legal.privacy_page.data_sharing_body2') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.international_title') }}</h2>
      <p>{{ t('legal.privacy_page.international_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.security_title') }}</h2>
      <p>{{ t('legal.privacy_page.security_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.your_rights_title') }}</h2>
      <p>{{ t('legal.privacy_page.your_rights_intro') }}</p>
      <ul>
        <li v-html="t('legal.privacy_page.your_rights_item_access')" />
        <li v-html="t('legal.privacy_page.your_rights_item_rectification')" />
        <li v-html="t('legal.privacy_page.your_rights_item_erasure')" />
        <li v-html="t('legal.privacy_page.your_rights_item_restriction')" />
        <li v-html="t('legal.privacy_page.your_rights_item_portability')" />
        <li v-html="t('legal.privacy_page.your_rights_item_objection')" />
      </ul>
      <p>
        {{ t('legal.privacy_page.your_rights_contact_before') }}<RouterLink to="/impressum" class="inline-link">{{ t('legal.privacy_page.your_rights_contact_link') }}</RouterLink>{{ t('legal.privacy_page.your_rights_contact_after') }}
      </p>
      <p>{{ t('legal.privacy_page.your_rights_supervisory') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.changes_title') }}</h2>
      <p>{{ t('legal.privacy_page.changes_body') }}</p>
    </section>

    <section>
      <h2>{{ t('legal.privacy_page.contact_title') }}</h2>
      <p>
        {{ t('legal.privacy_page.contact_body_before') }}<RouterLink to="/impressum" class="inline-link">{{ t('legal.privacy_page.contact_body_link') }}</RouterLink>{{ t('legal.privacy_page.contact_body_after') }}
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

strong { color: hsl(210, 40%, 88%); font-weight: 600; }

.controller-block {
  background: rgba(88, 101, 242, 0.07);
  border: 1px solid rgba(88, 101, 242, 0.2);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.controller-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: hsl(224, 76%, 70%);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0;
}

.inline-link {
  color: hsl(224, 76%, 70%);
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: color 0.15s;
}
.inline-link:hover { color: hsl(224, 100%, 82%); }
</style>
