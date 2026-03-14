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

      <h1 class="legal-title">{{ t("legal.terms") }}</h1>
      <p class="legal-meta">Last updated: March 2026</p>

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

      <div class="legal-footer">
        <RouterLink to="/privacy" class="legal-link">{{ t("legal.privacy") }}</RouterLink>
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
