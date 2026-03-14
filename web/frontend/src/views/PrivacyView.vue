<script setup lang="ts">
import { useI18n } from "@/i18n";
import LegalPageLayout from "@/components/LegalPageLayout.vue";

const { t, locale } = useI18n();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.privacy')"
    :back-text="t('legal.back')"
    footer-link-to="/terms"
    :footer-link-text="t('legal.terms')"
  >
    <template v-if="locale.current === 'de'">
      <section>
        <h2>1. Welche Daten wir erheben</h2>
        <p>NerpyBot erhebt und speichert die minimal notwendigen Daten, um seine Funktionen bereitzustellen:</p>
        <ul>
          <li><strong>Server-IDs</strong> — zur Zuordnung der Konfiguration zu deinem Server</li>
          <li><strong>Discord-Nutzer-IDs und Benutzernamen</strong> — für Dashboard-Zugang, Erinnerungen und Moderationsaktionen</li>
          <li><strong>Kanal- und Rollen-IDs</strong> — zur Zustellung von Nachrichten und Anwendung von Rollenzuweisungen gemäß deiner Konfiguration</li>
          <li><strong>Antworten auf Bewerbungsformulare</strong> — von Mitgliedern über das Bewerbungssystem des Bots eingereicht, zur Überprüfung durch Moderatoren gespeichert</li>
          <li><strong>Konfigurationsdaten</strong> — Einstellungen, die du über das Dashboard oder Bot-Befehle konfigurierst (z. B. Abschiedsnachrichten, Erinnerungspläne)</li>
        </ul>
        <p>Wir erheben keine allgemeinen Nachrichteninhalte, Sprachaudio oder sonstige Daten über das für konfigurierte Funktionen Erforderliche hinaus.</p>
      </section>

      <section>
        <h2>2. Wie wir deine Daten verwenden</h2>
        <p>Alle erhobenen Daten werden ausschließlich zur Bereitstellung der NerpyBot-Funktionalität auf deinem Server verwendet. Wir nutzen deine Daten nicht für Werbung, Analysen oder andere Zwecke als den Betrieb des Bots.</p>
      </section>

      <section>
        <h2>3. Datenspeicherung</h2>
        <p>Mit deinem Server verbundene Daten werden gespeichert, solange NerpyBot aktiv ist. Wenn du NerpyBot von deinem Server entfernst, kannst du die Löschung aller zugehörigen Daten durch Kontaktaufnahme mit einem Bot-Operator über Discord anfordern.</p>
        <p>Dashboard-Nutzerdaten (Discord-Nutzer-ID, Benutzername, Premium-Status) werden gespeichert, bis der Zugang durch einen Operator widerrufen wird.</p>
      </section>

      <section>
        <h2>4. Datenweitergabe</h2>
        <p>Wir verkaufen, vermieten oder teilen deine Daten nicht mit Dritten. Daten können offengelegt werden, wenn dies gesetzlich vorgeschrieben ist.</p>
        <p>NerpyBot integriert Drittanbieter-APIs (Blizzard, Riot Games), um auf Anfrage öffentliche Spieldaten abzurufen. Wir teilen deine Discord-Daten nicht mit diesen Diensten.</p>
      </section>

      <section>
        <h2>5. Datensicherheit</h2>
        <p>Wir treffen angemessene technische Maßnahmen zum Schutz gespeicherter Daten. Kein System ist jedoch vollständig sicher, und wir können keine absolute Sicherheit garantieren.</p>
      </section>

      <section>
        <h2>6. Deine Rechte</h2>
        <p>Du kannst jederzeit Auskunft über, Berichtigung oder Löschung deiner Daten anfordern, indem du dich über Discord an einen Bot-Operator wendest.</p>
      </section>

      <section>
        <h2>7. Änderungen dieser Richtlinie</h2>
        <p>Wir können diese Datenschutzerklärung von Zeit zu Zeit aktualisieren. Die weitere Nutzung des Dienstes nach Änderungen gilt als Zustimmung zur aktualisierten Richtlinie.</p>
      </section>

      <section>
        <h2>8. Kontakt</h2>
        <p>Für datenschutzbezogene Anfragen wende dich über Discord an einen Bot-Operator.</p>
      </section>
    </template>

    <template v-else>
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
    </template>
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
