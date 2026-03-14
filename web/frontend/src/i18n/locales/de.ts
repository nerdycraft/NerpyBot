import type { en } from "./en";

export const de: typeof en = {
  common: {
    loading: "Laden…",
    saving: "Speichern…",
    saved: "✓ Gespeichert",
    save: "Speichern",
    cancel: "Abbrechen",
    add: "Hinzufügen",
    adding: "Hinzufügen…",
    edit: "Bearbeiten",
    delete: "Löschen",
    remove: "Entfernen",
    create: "Erstellen",
    refresh: "Aktualisieren",
    enabled: "Aktiviert",
    disabled: "Deaktiviert",
    yes: "Ja",
    no: "Nein",
    revoke: "Widerrufen",
    unload: "Entladen",
    confirm: "Bestätigen",
    relative_never: "Nie",
    relative_today: "heute",
    relative_one_day_ago: "vor 1 Tag",
    relative_days_ago: "vor {days} Tagen",
    back: "Zurück",
    load_failed: "Laden fehlgeschlagen",
    save_failed: "Speichern fehlgeschlagen",
    delete_failed: "Löschen fehlgeschlagen",
  },

  nav: {
    groups: {
      general: "Allgemein",
      moderation: "Moderation",
      roles: "Rollen",
      applications: "Bewerbungen",
      wow: "WoW",
      support: "Support",
      operator: "Operator",
    },
    items: {
      server_overview: "Serverübersicht",
      language: "Sprache",
      reminders: "Erinnerungen",
      moderator_roles: "Moderatorrollen",
      auto_kicker: "Auto-Kicker",
      auto_delete: "Auto-Löschen",
      leave_messages: "Abschiedsnachrichten",
      role_mappings: "Rollenzuweisungen",
      reaction_roles: "Reaktionsrollen",
      application_forms: "Formulare",
      application_templates: "Vorlagen",
      application_submissions: "Einsendungen",
      wow_guild_news: "Gildennachrichten",
      wow_crafting: "Handwerkstafeln",
      support: "Kontakt & Feedback",
      operator_dashboard: "Bot-Status",
      operator_guilds: "Alle Server",
      operator_modules: "Module",
      operator_user_management: "Benutzerverwaltung",
    },
    sidebar: {
      all_servers: "Alle Server",
      logout: "Abmelden",
      collapse: "Seitenleiste einklappen",
      expand: "Seitenleiste ausklappen",
      open_nav: "Navigation öffnen",
      support_mode: "Support-Modus",
      support_mode_desc:
        "Ansicht als Operator. Sensible Inhalte sind verborgen. Schreibvorgänge sind deaktiviert.",
      guild_fallback: "Server",
    },
  },

  language_switcher: {
    aria_label: "Sprache: {lang}",
  },

  mockup: {
    title: "Mockup-Modus",
    simulating: "Ansicht simuliert als",
    exit: "Mockup beenden",
    simulate_as: "Ansicht simulieren als:",
    choose_level: "— Stufe wählen —",
    sections_hidden: "Einige Bereiche sind möglicherweise ausgeblendet.",
    levels: {
      admin: "Admin",
      mod: "Moderator",
      member: "Mitglied",
    },
  },

  legal: {
    terms: "Nutzungsbedingungen",
    privacy: "Datenschutzerklärung",
    back: "Zurück",
    last_updated: "Zuletzt aktualisiert: März 2026",
  },

  login: {
    subtitle: "Dashboard",
    tagline: "Mit deinem Discord-Konto anmelden, um deine Server zu verwalten.",
    login_btn: "Mit Discord anmelden",
    session_expired_with_user: "Hey {username}, deine Sitzung ist abgelaufen.",
    session_expired: "Deine Sitzung ist abgelaufen.",
    session_expired_hint: "Bitte melde dich erneut an, um fortzufahren.",
    dismiss: "Schließen",
    premium_required: "Premium erforderlich",
    premium_required_desc:
      "Dashboard-Zugang ist eine Premium-Funktion. Wende dich an einen Bot-Operator, um Zugang zu beantragen.",
  },

  tabs: {
    language: {
      title: "Sprache",
      desc: "Steuert die Sprache, die NerpyBot für alle Antworten in diesem Server verwendet, einschließlich Befehlsantworten, Embeds und automatischer Nachrichten. Änderungen werden sofort übernommen und automatisch gespeichert.",
      label: "Sprache",
      tooltip: "Die Sprache, die NerpyBot bei Antworten auf diesem Server verwendet (z. B. English, Deutsch).",
      en: "English",
      de: "Deutsch",
    },

    reaction_roles: {
      title: "Reaktionsrollen",
      desc: "Reaktionsrollen ermöglichen es Mitgliedern, sich Discord-Rollen selbst zuzuweisen, indem sie auf eine bestimmte Nachricht mit einem festgelegten Emoji reagieren – jedes Emoji entspricht genau einer Rolle. Diese Ansicht ist schreibgeschützt; Einträge werden direkt in Discord über Bot-Befehle verwaltet.",
      empty: "Keine Reaktionsrollen-Nachrichten konfiguriert.",
      message_ref: "#{channel} · Nachricht {id}",
    },

    moderator_roles: {
      title: "Moderatorrollen",
      desc: "Weise Discord-Rollen als NerpyBot-Moderatoren zu — Mitglieder mit einer der aufgelisteten Rollen können Moderationsbefehle wie Kick, Ban und Nachrichtenbereinigung nutzen. Du kannst beliebig viele Rollen hinzufügen; Änderungen treten sofort in Kraft.",
      empty: "Keine Moderatorrollen konfiguriert.",
      role_label: "Rolle",
      role_tooltip:
        "Die Discord-Rolle, die Bot-Moderatorrechte erhält. Mitglieder mit dieser Rolle können Moderationsbefehle ausführen.",
    },

    leave_messages: {
      title: "Abschiedsnachrichten",
      desc: "Sende eine benutzerdefinierte Nachricht in einen Kanal, wenn ein Mitglied den Server verlässt oder entfernt wird. Verwende {user} im Nachrichtentext, um das abgehende Mitglied namentlich zu erwähnen.",
      enabled_tooltip:
        "Wenn aktiviert, postet der Bot jedes Mal eine Abschiedsnachricht, wenn ein Mitglied den Server verlässt oder entfernt wird.",
      channel_label: "Kanal",
      channel_tooltip:
        "Der Textkanal, in dem Abschiedsnachrichten gepostet werden. Der Bot muss die Berechtigung haben, in diesem Kanal Nachrichten zu senden.",
      message_label: "Nachricht",
      message_tooltip:
        "Der Nachrichtentext beim Verlassen des Servers. Verwende {user} als Platzhalter — er wird durch den Benutzernamen des abgehenden Mitglieds ersetzt.",
      placeholder: "Auf Wiedersehen {user}!",
    },

    support: {
      title: "Kontakt & Feedback",
      desc: "Sende einen Fehlerbericht, eine Funktionsanfrage oder allgemeines Feedback an die Bot-Operatoren. Nachrichten werden direkt per Discord-DM zugestellt.",
      success_one: "Nachricht erfolgreich an {count} Operator gesendet.",
      success_many: "Nachricht erfolgreich an {count} Operatoren gesendet.",
      send_another: "Weitere senden",
      category_label: "Kategorie",
      message_label: "Nachricht",
      message_hint: "(10–2000 Zeichen)",
      placeholder: "Beschreibe dein Problem oder deine Idee…",
      char_count: "{count} / 2000",
      submit: "Nachricht senden",
      submitting: "Senden…",
      send_failed: "Nachricht konnte nicht gesendet werden",
      category: {
        bug: "Fehlerbericht",
        feature: "Funktionsanfrage",
        feedback: "Feedback",
        other: "Sonstiges",
      },
    },

    auto_kicker: {
      title: "Auto-Kicker",
      desc: "Kickt automatisch Mitglieder, die sich innerhalb einer konfigurierbaren Anzahl von Tagen nicht verifiziert oder keine Aktivität gezeigt haben. Der Bot sendet bei Bedarf eine optionale Erinnerungsnachricht vor dem Kick.",
      enabled_tooltip:
        "Wenn deaktiviert, werden keine Mitglieder gekickt, unabhängig von den anderen Einstellungen.",
      kick_after_label: "Kick nach (Tagen)",
      kick_after_tooltip:
        "Anzahl der Inaktivitätstage, bevor ein Mitglied gekickt wird. Muss mindestens 1 sein.",
      kick_after_validation: "Kick-nach-Tagen muss mindestens 1 betragen.",
      reminder_label: "Erinnerungsnachricht (optional)",
      reminder_tooltip:
        "Falls gesetzt, schickt NerpyBot dem Mitglied diese Nachricht per DM, bevor es gekickt wird. Leer lassen für stillen Kick.",
      placeholder: "Du wirst bald wegen Inaktivität gekickt…",
    },

    auto_delete: {
      title: "Auto-Löschen",
      desc: "Löscht automatisch Nachrichten in bestimmten Kanälen, sobald sie ein konfiguriertes Alter oder eine Nachrichtenanzahl überschreiten. Jede Regel zielt auf einen Kanal ab — füge beliebig viele Regeln hinzu und aktiviere oder deaktiviere sie ohne sie zu löschen.",
      empty: "Keine Auto-Lösch-Regeln konfiguriert.",
      add_rule: "Regel hinzufügen",
      channel_label: "Kanal",
      channel_tooltip:
        "Der Kanal, in dem automatisches Löschen angewendet wird. Jeder Kanal kann nur eine Regel haben.",
      keep_label: "Nachrichten behalten",
      keep_tooltip:
        "Immer mindestens diese Anzahl neuerer Nachrichten im Kanal behalten, unabhängig vom Alter. Auf 0 setzen, um zu deaktivieren.",
      older_label: "Älter als (s)",
      older_tooltip:
        "Nachrichten löschen, die älter als diese Anzahl von Sekunden sind. Auf 0 setzen, um nur das Behalten-Limit zu verwenden.",
      delete_pinned_label: "Angeheftete löschen",
      delete_pinned_tooltip:
        "Wenn aktiviert, unterliegen auch angeheftete Nachrichten in diesem Kanal dem Löschen. Standardmäßig werden angeheftete Nachrichten behalten.",
      keep_display: "Behalten: {count} Nachrichten",
      older_display: "Älter als: {seconds}s",
      delete_pinned_display: "Angeheftete löschen: {value}",
    },

    role_mappings: {
      title: "Rollenzuweisungen",
      desc: "Delegiere die Rollenzuweisung an bestimmte Rollen — jede Zuordnung gibt Mitgliedern der Quellrolle die Möglichkeit, die Zielrolle anderen über Bot-Befehle zuzuweisen. Mehrere Zuordnungen können dieselbe Quell- oder Zielrolle teilen.",
      empty: "Keine Rollenzuweisungen konfiguriert.",
      source_label: "Quellrolle",
      source_tooltip:
        "Die Rolle, deren Mitglieder die Zielrolle anderen über Bot-Befehle zuweisen dürfen.",
      source_placeholder: "Quellrolle…",
      target_label: "Zielrolle",
      target_tooltip:
        "Die Rolle, die Mitgliedern zugewiesen wird, wenn ein Benutzer mit der Quellrolle den Zuweisungsbefehl ausführt.",
      target_placeholder: "Zielrolle…",
    },

    server_overview: {
      title: "Deine Server",
      desc: 'Alle Server, auf denen NerpyBot aktiv ist und du Zugang zum Dashboard hast. Klicke auf eine Karte, um zu den Einstellungen dieses Servers zu springen — der aktuell ausgewählte Server ist mit einem „Aktuell"-Badge hervorgehoben.',
      empty: "NerpyBot ist noch auf keinem deiner Server.",
      current: "Aktuell",
      add_title: "Zu einem Server hinzufügen",
      add_desc: "Du hast ausreichende Berechtigungen, um NerpyBot auf diesen Servern einzuladen.",
      invite: "Einladen",
    },

    operator_guilds: {
      title: "Alle Bot-Server",
      desc: "Server, auf denen der Bot aktiv ist, für die du aber keine Verwaltungsrechte hast. Klicke auf einen Server, um ihn im Support-Modus zu öffnen.",
      loading: "Server werden geladen…",
      empty: "Keine Server gefunden.",
      count_one: "{count} Server insgesamt",
      count_many: "{count} Server insgesamt",
      members: "{count} Mitglieder",
    },

    operator_modules: {
      title: "Modulsteuerung",
      desc: "Module zur Laufzeit laden und entladen. Änderungen treten sofort in Kraft, bleiben aber nicht über Neustarts hinaus bestehen.",
      loaded_modules: "Geladene Module",
      loaded_count: "{count} geladen",
      loading: "Laden…",
      empty: "Keine Module geladen oder Bot nicht erreichbar.",
      protected: "geschützt",
      unload: "Entladen",
      load_section: "Modul laden",
      all_loaded: "Alle verfügbaren Module sind bereits geladen.",
      select: "Modul auswählen…",
      load: "Laden",
    },

    operator_user_management: {
      title: "Benutzerverwaltung",
      desc: "Gewähre oder entziehe Discord-Nutzern den Dashboard-Zugang. Nutzer mit Premium-Status können sich anmelden und Server verwalten, für die sie Berechtigungen haben; ohne Premium werden sie zur Anmeldeseite weitergeleitet.",
      empty: "Noch keine Premium-Nutzer.",
      discord_id_label: "Discord-Nutzer-ID",
      discord_id_tooltip:
        "Die 18-stellige Discord-Snowflake-ID des Nutzers, dem Zugang gewährt werden soll. Du findest sie, indem du den Entwicklermodus in Discord aktivierst und mit der rechten Maustaste auf den Nutzer klickst.",
      discord_id_placeholder: "z. B. 123456789012345678",
      revoke: "Widerrufen",
      grant: "Zugang gewähren",
      granting: "Gewähren…",
      since: "seit {date}",
    },

    operator_dashboard: {
      title: "Bot-Status",
      desc: "Live-Metriken der laufenden Bot-Instanz.",
      auto_refresh: "Auto-Aktualisierung (30s)",
      loading: "Statusdaten werden geladen…",
      unreachable:
        "Bot nicht erreichbar — der Bot-Prozess ist möglicherweise offline oder antwortet nicht.",
      status: "Status:",
      online: "Online",
      status_unreachable: "Nicht erreichbar",
      uptime: "Laufzeit",
      latency: "Latenz",
      guilds: "Server",
      active_reminders: "Aktive Erinnerungen",
      errors_24h: "Fehler (24h)",
      memory: "Speicher",
      cpu: "CPU",
      voice_connections: "Sprachverbindungen",
      version_info: "Versionsinformationen",
      bot_version: "Bot-Version",
      python: "Python",
      discord_py: "discord.py",
      active_voice_sessions: "Aktive Sprachsitzungen",
      col_guild: "Server",
      col_channel: "Kanal",
      fetch_failed: "Statusdaten konnten nicht abgerufen werden",
    },

    reminders: {
      title: "Erinnerungen",
      desc: "Erinnerungen posten eine Nachricht in einem Discord-Kanal nach einem wiederkehrenden Zeitplan — alle N Minuten/Stunden/Tage, täglich, wöchentlich oder monatlich. Jede Erinnerung kann einzeln aktiviert oder deaktiviert werden; der Bot verfolgt, wie oft jede ausgelöst wurde und wann die nächste fällig ist.",
      new: "Neue Erinnerung",
      new_panel: "Neue Erinnerung",
      empty: "Keine Erinnerungen konfiguriert.",
      channel_label: "Kanal",
      channel_tooltip: "Der Discord-Kanal, in dem die Erinnerungsnachricht gepostet wird.",
      schedule_type_label: "Zeitplantyp",
      schedule_type_tooltip:
        "Wie oft die Erinnerung ausgelöst wird: ein sich wiederholendes Intervall oder eine feste Zeit täglich, wöchentlich oder monatlich.",
      repeat_label: "Alle wiederholen",
      repeat_tooltip:
        "Das Intervall zwischen den Auslösungen. Gib eine Zahl ein und wähle Minuten, Stunden oder Tage.",
      time_label: "Uhrzeit",
      time_tooltip:
        "Die Tageszeit, zu der die Erinnerung ausgelöst wird, interpretiert in der ausgewählten Zeitzone.",
      dow_label: "Wochentag",
      dow_tooltip: "An welchem Wochentag die Erinnerung für wöchentliche Zeitpläne ausgelöst wird.",
      dom_label: "Tag im Monat (1–28)",
      dom_tooltip:
        "An welchem Tag des Monats die Erinnerung ausgelöst wird. Begrenzt auf 28, damit sie jeden Monat ausgelöst wird.",
      tz_label: "Zeitzone",
      tz_tooltip:
        "Die Zeitzone zur Interpretation der Zeitplanzeit. Standardmäßig UTC, wenn leer gelassen.",
      message_label: "Nachricht",
      message_tooltip:
        "Der Textinhalt, der jedes Mal in den Kanal gepostet wird, wenn die Erinnerung ausgelöst wird.",
      saving: "Speichern…",
      type: {
        interval: "Alle wiederholen…",
        daily: "Täglich zu einer festen Uhrzeit",
        weekly: "Wöchentlich (Tag + Uhrzeit)",
        monthly: "Monatlich (Tag + Uhrzeit)",
      },
      unit: {
        minutes: "Minuten",
        hours: "Stunden",
        days: "Tage",
      },
      days: {
        monday: "Montag",
        tuesday: "Dienstag",
        wednesday: "Mittwoch",
        thursday: "Donnerstag",
        friday: "Freitag",
        saturday: "Samstag",
        sunday: "Sonntag",
      },
      schedule: {
        interval: "Alle {interval}",
        daily: "Täglich um {time}",
        weekly: "Wöchentlich · {dow} um {time}",
        monthly: "Monatlich · Tag {dom} um {time}",
      },
      next_fire: "Nächste: {datetime}",
      fired_count: "{count}× ausgelöst",
      enable: "Aktivieren",
      disable: "Deaktivieren",
      tz_placeholder: "Zeitzone suchen…",
      message_placeholder: "Nachricht, die im Kanal gepostet wird…",
      no_message: "(keine Nachricht)",
    },

    application_submissions: {
      title: "Einsendungen",
      desc: "Durchsuche alle Bewerbungseinsendungen von Servermitgliedern, einschließlich ihrer Antworten, des aktuellen Status und der Moderatorenstimmen. Diese Ansicht ist schreibgeschützt — Zustimmungen und Ablehnungen werden von Moderatoren direkt im Überprüfungskanal auf Discord abgegeben.",
      form_label: "Formular",
      form_tooltip:
        "Einsendungen filtern, um nur die eines bestimmten Bewerbungsformulars anzuzeigen.",
      status_label: "Status",
      status_tooltip:
        "Einsendungen nach ihrem aktuellen Überprüfungsstatus filtern: ausstehend (wartet auf Stimmen), genehmigt von Moderatoren oder abgelehnt.",
      all_forms: "Alle Formulare",
      empty: "Keine Einsendungen.",
      select_hint: "Wähle eine Einsendung, um Details anzuzeigen.",
      status: {
        all: "Alle",
        pending: "Ausstehend",
        approved: "Genehmigt",
        denied: "Abgelehnt",
      },
      answers: "Antworten",
      no_answers: "Keine Antworten.",
      votes: "Stimmen",
      no_votes: "Keine Stimmen aufgezeichnet.",
      approved_count: "Genehmigt ({count})",
      denied_count: "Abgelehnt ({count})",
      decision_reason: "Entscheidungsbegründung",
      submitted: "Eingereicht {datetime}",
      total: "{count} gesamt",
    },

    application_templates: {
      title: "Vorlagen",
      desc: "Vorlagen sind wiederverwendbare Fragensätze, die über mehrere Bewerbungsformulare hinweg geteilt werden können, sodass du gemeinsame Fragenkataloge einmal definieren und überall anwenden kannst. Eingebaute Vorlagen werden vom Bot bereitgestellt und können nicht geändert oder gelöscht werden.",
      new: "Neue Vorlage",
      new_panel: "Neue Vorlage",
      empty: "Keine Vorlagen.",
      name_label: "Name",
      name_tooltip:
        "Ein eindeutiger Name für diese Vorlage. Wird bei der Auswahl einer Vorlage als Basis für ein neues Formular angezeigt.",
      questions_label: "Fragen",
      questions_tooltip:
        "Die Fragen, die Mitgliedern gestellt werden, wenn sie ein Formular ausfüllen, das diese Vorlage verwendet. Fragen werden der Reihe nach per DM präsentiert.",
      add_question: "+ Frage hinzufügen",
      built_in: "Standard",
      saving: "Speichern…",
      questions_count: { one: "1 Frage", other: "{count} Fragen" },
      question_placeholder: "Frage {num}…",
      new_question_placeholder: "Neue Frage…",
      delete_confirm: "Diese Vorlage löschen?",
    },

    application_forms: {
      title: "Formulare",
      desc: "Bewerbungsformulare definieren die Fragen, die Mitglieder beim Bewerben über den Bot per DM beantworten. Jedes Formular benötigt mindestens eine Frage und einen Überprüfungskanal, in dem Moderatoren Zustimmungs-/Ablehnungsstimmen abgeben.",
      new: "Neues Formular",
      new_panel: "Neues Formular",
      empty: "Noch keine Formulare.",
      name_label: "Name",
      name_tooltip:
        "Ein eindeutiger, lesbarer Name für dieses Formular, der im Dashboard und auf dem Bewerben-Button-Embed angezeigt wird.",
      name_placeholder: "z. B. Gilden-Bewerbung",
      review_channel_label: "Überprüfungskanal",
      review_channel_tooltip:
        "Der Discord-Kanal, in dem der Bot Einsendungs-Embeds postet und Moderatoren Stimmen abgeben.",
      apply_channel_label: "Bewerbungskanal",
      apply_channel_tooltip:
        "Der Discord-Kanal, in dem der Bot den dauerhaften Bewerben-Button postet, den Mitglieder zum Starten ihrer Bewerbung anklicken.",
      apply_desc_label: "Bewerbungsbeschreibung",
      apply_desc_tooltip:
        "Optionaler Text auf dem Bewerben-Button-Embed, der die Bewerbung beschreibt oder Erwartungen für Bewerber setzt.",
      required_approvals_label: "Erforderliche Zustimmungen",
      required_approvals_tooltip:
        "Anzahl der Moderatoren-Zustimmungsstimmen, die benötigt werden, um die Bewerbung automatisch anzunehmen.",
      required_denials_label: "Erforderliche Ablehnungen",
      required_denials_tooltip:
        "Anzahl der Moderatoren-Ablehnungsstimmen, die benötigt werden, um die Bewerbung automatisch abzulehnen.",
      approval_message_label: "Zustimmungsnachricht",
      approval_message_tooltip:
        "Optionale Nachricht, die der Bot dem Bewerber per DM sendet, wenn seine Bewerbung genehmigt wurde.",
      denial_message_label: "Ablehnungsnachricht",
      denial_message_tooltip:
        "Optionale Nachricht, die der Bot dem Bewerber per DM sendet, wenn seine Bewerbung abgelehnt wurde.",
      questions: "Fragen",
      no_questions: "Noch keine Fragen.",
      view_submissions: "Einsendungen anzeigen",
      saving: "Speichern…",
      edit_settings: "Einstellungen bearbeiten",
      review_channel_summary: "Überprüfungskanal: #{channel}",
      apply_channel_summary: "Bewerbungskanal: #{channel}",
      approval_message_set: "Zustimmungsnachricht gesetzt",
      denial_message_set: "Ablehnungsnachricht gesetzt",
      new_question_placeholder: "Neue Frage…",
      questions_count: "{count} Fragen",
      delete_confirm: "Dieses Formular und alle Einsendungen löschen?",
    },

    wow_guild_news: {
      title: "Gildennachrichten",
      desc: "Verfolge die Aktivität einer World-of-Warcraft-Gilde — Boss-Kills, Mitgliedsbeitritte und -abgänge sowie Erfolge — und poste Updates automatisch in einem Discord-Kanal. Jeder Tracker zielt auf eine Gilde auf einem bestimmten Realm ab und verarbeitet nur Charaktere, die innerhalb des konfigurierten Zeitfensters aktiv waren.",
      add: "Tracker hinzufügen",
      cancel_add: "Abbrechen",
      empty: "Keine Gildennachrichten-Tracker konfiguriert.",
      new_tracker: "Neuer Tracker",
      region_label: "Region",
      region_tooltip:
        "Die WoW-Region, auf der sich deine Gilde befindet (EU oder US). Dadurch wird bestimmt, welcher Blizzard-API-Endpunkt abgefragt wird.",
      guild_name_label: "WoW-Gildenname",
      guild_name_tooltip:
        "Der genaue In-Game-Name der zu verfolgenden WoW-Gilde. Der Bot überprüft, ob diese Gilde auf dem gewählten Realm existiert, bevor er speichert.",
      realm_label: "Realm",
      realm_tooltip:
        "Der WoW-Realm (Server), auf dem sich die Gilde befindet. Muss zur ausgewählten Region passen.",
      channel_label: "Kanal",
      channel_tooltip:
        "Der Discord-Kanal, in dem Gildennachrichten-Updates gepostet werden. Der Bot muss die Berechtigung haben, dort Nachrichten zu senden.",
      active_days_label: "Aktive Tage",
      active_days_tooltip:
        "Nur Charaktere, die innerhalb dieser Anzahl von Tagen im Spiel gesehen wurden, gelten als aktiv und werden in die Nachrichtenverfolgung einbezogen.",
      min_level_label: "Mindestlevel",
      min_level_tooltip:
        "Charaktere unterhalb dieses Levels werden ignoriert. Nützlich, um niedrigstufige Twinks aus Beiträgen herauszufiltern.",
      required_fields: "Region, Gildenname, Realm und Kanal sind erforderlich.",
      guild_name_placeholder: "z. B. Thunderfury",
      guild_not_found: "Gilde auf diesem Realm nicht gefunden. Überprüfe Gildenname und Realm.",
      verify_warning: "Gilde kann nicht verifiziert werden (Bot offline). Trotzdem speichern?",
      save_anyway: "Trotzdem speichern",
      saving: "Speichern…",
      status: {
        active: "Aktiv",
        disabled: "Deaktiviert",
      },
      delete_confirm: "Diesen Tracker löschen?",
      show_roster: "Kader anzeigen",
      hide_roster: "Kader ausblenden",
      loading_roster: "Kader wird geladen…",
      no_roster: "Noch keine Charakterdaten.",
      col_character: "Charakter",
      col_realm: "Realm",
      col_mounts: "Reittiere",
      col_last_checked: "Zuletzt geprüft",
      last_news: "Letzte Neuigkeit: {time}",
      tracked_chars: "{count} verfolgte Charaktere",
      active_days_display: "Aktive Tage: {days}",
      min_level_display: "Mindestlevel: {level}",
      validation_failed: "Validierung fehlgeschlagen",
    },

    wow_crafting: {
      title: "Handwerkstafeln",
      desc: "Das Handwerkstafel-System überwacht World-of-Warcraft-Handwerksauftragswarteschlangen und postet neue Aufträge in einem konfigurierten Discord-Kanal. Verwende Rollenzuweisungen, um Discord-Rollen mit WoW-Berufen zu verknüpfen, damit der Bot die richtigen Handwerker benachrichtigen kann.",
      board: "Tafel",
      no_board: "Keine Handwerkstafel konfiguriert.",
      role_mappings: "Rolle → Beruf-Zuweisungen",
      role_mappings_desc:
        "Ordne Discord-Rollen WoW-Berufen zu, damit Handwerker passende Aufträge annehmen können.",
      no_mappings: "Noch keine Zuweisungen.",
      role_label: "Rolle",
      role_tooltip:
        "Die Discord-Rolle, die mit einem WoW-Beruf verknüpft wird. Mitglieder mit dieser Rolle werden benachrichtigt, wenn ein passender Handwerksauftrag erscheint.",
      profession_label: "Beruf",
      profession_tooltip:
        "Der WoW-Beruf, den diese Rolle abdeckt. Der Bot benachrichtigt die zugeordnete Rolle, wenn ein Handwerksauftrag für diesen Beruf erkannt wird.",
      select_role: "Rolle auswählen…",
      select_profession: "Beruf auswählen…",
      orders: "Aufträge",
      loading_orders: "Aufträge werden geladen…",
      no_orders: "Keine Aufträge gefunden.",
      order_by: "von {name}",
      order_crafter: "Handwerker: {name}",
      status: {
        all: "Alle",
        open: "Offen",
        in_progress: "In Bearbeitung",
        completed: "Abgeschlossen",
        cancelled: "Abgebrochen",
      },
      profession: {
        blacksmithing: "Schmiedekunst",
        leatherworking: "Lederverarbeitung",
        tailoring: "Schneiderei",
        engineering: "Ingenieurskunst",
        enchanting: "Verzauberkunst",
        alchemy: "Alchemie",
        inscription: "Inschriftenkunde",
        jewelcrafting: "Juwelenschleifen",
        cooking: "Kochen",
      },
    },
  },
};
