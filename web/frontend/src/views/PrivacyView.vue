<script setup lang="ts">
import { RouterLink } from "vue-router";
import { useI18n } from "@/i18n";

const { t } = useI18n();
</script>

<template>
  <div class="legal-bg" aria-hidden="true" />

  <div class="min-h-screen relative z-10 px-4 py-12">
    <div class="legal-card">
      <RouterLink to="/login" class="back-link">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 12H5M12 5l-7 7 7 7" />
        </svg>
        {{ t("legal.back") }}
      </RouterLink>

      <h1 class="legal-title">{{ t("legal.privacy") }}</h1>
      <p class="legal-meta">Last updated: March 2026</p>

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

      <div class="legal-footer">
        <RouterLink to="/terms" class="legal-link">{{ t("legal.terms") }}</RouterLink>
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
