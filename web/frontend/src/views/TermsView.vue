<script setup lang="ts">
import { useI18n } from "@/i18n";
import LegalPageLayout from "@/components/LegalPageLayout.vue";

const { t } = useI18n();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.terms')"
    :back-text="t('legal.back')"
    footer-link-to="/privacy"
    :footer-link-text="t('legal.privacy')"
  >
    <section>
      <h2>1. Acceptance of Terms</h2>
      <p>By adding NerpyBot to your Discord server or using the NerpyBot dashboard, you agree to these Terms of Service. If you do not agree, do not use the service.</p>
    </section>

    <section>
      <h2>2. Description of Service</h2>
      <p>NerpyBot is a Discord bot that provides server management, moderation, gaming integrations (World of Warcraft, League of Legends), application forms, role management, and related features. A web dashboard is available to server administrators with premium access.</p>
    </section>

    <section>
      <h2>3. Acceptable Use</h2>
      <p>You agree not to use NerpyBot to:</p>
      <ul>
        <li>Violate Discord's Terms of Service or Community Guidelines</li>
        <li>Harass, threaten, or harm other users</li>
        <li>Attempt to exploit, hack, or disrupt the service</li>
        <li>Use the service for any unlawful purpose</li>
      </ul>
    </section>

    <section>
      <h2>4. Access and Availability</h2>
      <p>We reserve the right to remove NerpyBot from any server or revoke dashboard access at any time, with or without notice, particularly in cases of abuse or violation of these terms. We do not guarantee continuous, uninterrupted availability of the service.</p>
    </section>

    <section>
      <h2>5. Disclaimer of Warranties</h2>
      <p>NerpyBot is provided "as is" without warranties of any kind. We make no guarantees about the reliability, accuracy, or fitness for a particular purpose of the service.</p>
    </section>

    <section>
      <h2>6. Limitation of Liability</h2>
      <p>To the fullest extent permitted by law, we are not liable for any indirect, incidental, or consequential damages arising from your use of NerpyBot.</p>
    </section>

    <section>
      <h2>7. Changes to Terms</h2>
      <p>We may update these terms at any time. Continued use of the service after changes constitutes acceptance of the updated terms.</p>
    </section>

    <section>
      <h2>8. Contact</h2>
      <p>For questions about these terms, contact a bot operator through Discord.</p>
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
</style>
