<script setup lang="ts">
import { useI18n } from "@/i18n";
import LegalPageLayout from "@/components/LegalPageLayout.vue";

const { t, locale } = useI18n();
</script>

<template>
  <LegalPageLayout
    :title="t('legal.terms')"
    :back-text="t('legal.back')"
    footer-link-to="/privacy"
    :footer-link-text="t('legal.privacy')"
  >
    <template v-if="locale.current === 'de'">
      <section>
        <h2>1. Annahme der Nutzungsbedingungen</h2>
        <p>Durch das Hinzufügen von NerpyBot zu deinem Discord-Server oder die Nutzung des NerpyBot-Dashboards stimmst du diesen Nutzungsbedingungen zu. Wenn du nicht einverstanden bist, nutze den Dienst nicht.</p>
      </section>

      <section>
        <h2>2. Beschreibung des Dienstes</h2>
        <p>NerpyBot ist ein Discord-Bot, der Serververwaltung, Moderation, Gaming-Integrationen (World of Warcraft, League of Legends), Bewerbungsformulare, Rollenverwaltung und weitere Funktionen bereitstellt. Ein Web-Dashboard steht Serveradministratoren mit Premium-Zugang zur Verfügung.</p>
      </section>

      <section>
        <h2>3. Zulässige Nutzung</h2>
        <p>Du stimmst zu, NerpyBot nicht zu verwenden, um:</p>
        <ul>
          <li>Discords Nutzungsbedingungen oder Community-Richtlinien zu verletzen</li>
          <li>Andere Nutzer zu belästigen, zu bedrohen oder zu schädigen</li>
          <li>Den Dienst zu missbrauchen, zu hacken oder zu stören</li>
          <li>Den Dienst für gesetzwidrige Zwecke zu nutzen</li>
        </ul>
      </section>

      <section>
        <h2>4. Zugang und Verfügbarkeit</h2>
        <p>Wir behalten uns das Recht vor, NerpyBot jederzeit und ohne Vorankündigung von jedem Server zu entfernen oder den Dashboard-Zugang zu widerrufen, insbesondere bei Missbrauch oder Verstoß gegen diese Bedingungen. Wir garantieren keine kontinuierliche, ununterbrochene Verfügbarkeit des Dienstes.</p>
      </section>

      <section>
        <h2>5. Gewährleistungsausschluss</h2>
        <p>NerpyBot wird „wie besehen" ohne jegliche Gewährleistung bereitgestellt. Wir übernehmen keine Garantie für die Zuverlässigkeit, Genauigkeit oder Eignung für einen bestimmten Zweck des Dienstes.</p>
      </section>

      <section>
        <h2>6. Haftungsbeschränkung</h2>
        <p>Im gesetzlich zulässigen Umfang haften wir nicht für mittelbare, zufällige oder Folgeschäden, die aus der Nutzung von NerpyBot entstehen.</p>
      </section>

      <section>
        <h2>7. Änderungen der Nutzungsbedingungen</h2>
        <p>Wir können diese Bedingungen jederzeit aktualisieren. Die weitere Nutzung des Dienstes nach Änderungen gilt als Zustimmung zu den aktualisierten Bedingungen.</p>
      </section>

      <section>
        <h2>8. Kontakt</h2>
        <p>Bei Fragen zu diesen Bedingungen wende dich über Discord an einen Bot-Operator.</p>
      </section>
    </template>

    <template v-else>
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
</style>
