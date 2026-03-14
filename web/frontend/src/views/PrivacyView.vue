<script setup lang="ts">
import { useI18n } from "@/i18n";
import LegalPageLayout from "@/components/LegalPageLayout.vue";

const { t } = useI18n();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.privacy')"
    :back-text="t('legal.back')"
    footer-link-to="/terms"
    :footer-link-text="t('legal.terms')"
  >
    <section>
      <h2>1. What Data We Collect</h2>
      <p>NerpyBot collects and stores the minimum data necessary to provide its features:</p>
      <ul>
        <li><strong>Guild (server) IDs</strong> — to associate configuration with your server</li>
        <li><strong>Discord User IDs and usernames</strong> — for dashboard access, reminders, and moderation actions</li>
        <li><strong>Channel and role IDs</strong> — to deliver messages and apply role assignments per your configuration</li>
        <li><strong>Application form answers</strong> — submitted by members via the bot's application system, stored for moderator review</li>
        <li><strong>Configuration data</strong> — settings you choose to configure through the dashboard or bot commands (e.g. leave messages, reminder schedules)</li>
      </ul>
      <p>We do not collect general message content, voice audio, or any data beyond what is required for configured features.</p>
    </section>

    <section>
      <h2>2. How We Use Your Data</h2>
      <p>All collected data is used solely to provide NerpyBot's functionality within your server. We do not use your data for advertising, analytics, or any purpose beyond operating the bot.</p>
    </section>

    <section>
      <h2>3. Data Retention</h2>
      <p>Data associated with your server is retained while NerpyBot is active in it. If you remove NerpyBot from your server, you may request deletion of all associated data by contacting a bot operator through Discord.</p>
      <p>Dashboard user data (Discord User ID, username, premium status) is retained until access is revoked by an operator.</p>
    </section>

    <section>
      <h2>4. Data Sharing</h2>
      <p>We do not sell, rent, or share your data with third parties. Data may be disclosed if required by law.</p>
      <p>NerpyBot integrates with third-party APIs (Blizzard, Riot Games) to fetch public game data on request. We do not share your Discord data with these services.</p>
    </section>

    <section>
      <h2>5. Data Security</h2>
      <p>We take reasonable technical measures to protect stored data. However, no system is completely secure and we cannot guarantee absolute security.</p>
    </section>

    <section>
      <h2>6. Your Rights</h2>
      <p>You may request access to, correction of, or deletion of your data at any time by contacting a bot operator through Discord.</p>
    </section>

    <section>
      <h2>7. Changes to This Policy</h2>
      <p>We may update this Privacy Policy from time to time. Continued use of the service after changes constitutes acceptance of the updated policy.</p>
    </section>

    <section>
      <h2>8. Contact</h2>
      <p>For privacy-related requests, contact a bot operator through Discord.</p>
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
</style>
