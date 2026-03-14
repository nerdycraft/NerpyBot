/**
 * Test mode mock resolver.
 *
 * Matches API paths to fixture data and returns synthetic responses.
 * Mutable in-memory maps are seeded from fixtures so session changes
 * (add/delete) are reflected within the current browser session.
 */

import {
  CHANNELS,
  ROLES,
  guild1Language,
  guild1ModRoles,
  guild1LeaveMessages,
  guild1AutoDelete,
  guild1AutoKicker,
  guild1Reminders,
  guild1ReactionRoles,
  guild1RoleMappings,
  guild1ApplicationForms,
  guild1ApplicationTemplates,
  guild1ApplicationSubmissions,
  guild1WowGuildNews,
  guild1CraftingBoard,
  guild1CraftingMappings,
  guild1CraftingOrders,
  guild2Language,
  guild2ModRoles,
  guild2LeaveMessages,
  guild2AutoDelete,
  guild2AutoKicker,
  guild2Reminders,
  guild2ReactionRoles,
  guild2RoleMappings,
  guild2ApplicationForms,
  guild2ApplicationTemplates,
  guild2ApplicationSubmissions,
  guild2WowGuildNews,
  guild3Info,
  guild3Language,
  guild3ModRoles,
  guild3LeaveMessages,
  guild3AutoDelete,
  guild3AutoKicker,
  guild3Reminders,
  operatorHealth,
  operatorModules,
  operatorBotGuilds,
  operatorPremiumUsers,
} from "./fixtures";

// ── In-memory stores (seeded from fixtures, mutated by POST/PUT/DELETE) ──────

let _nextId = 100;
function nextId(): number {
  return ++_nextId;
}

const stores: Record<string, Record<string, unknown>> = {
  "999000000000000001": {
    modRoles: [...guild1ModRoles],
    autoDelete: [...guild1AutoDelete],
    reminders: [...guild1Reminders],
    reactionRoles: [...guild1ReactionRoles],
    roleMappings: [...guild1RoleMappings],
    applicationForms: [...guild1ApplicationForms],
    applicationTemplates: [...guild1ApplicationTemplates],
    applicationSubmissions: [...guild1ApplicationSubmissions],
    wowGuildNews: [...guild1WowGuildNews],
    craftingBoard: { ...guild1CraftingBoard },
    craftingMappings: [...guild1CraftingMappings],
    craftingOrders: [...guild1CraftingOrders],
    leaveMessages: { ...guild1LeaveMessages },
    autoKicker: { ...guild1AutoKicker },
    language: { ...guild1Language },
  },
  "999000000000000002": {
    modRoles: [...guild2ModRoles],
    autoDelete: [...guild2AutoDelete],
    reminders: [...guild2Reminders],
    reactionRoles: [...guild2ReactionRoles],
    roleMappings: [...guild2RoleMappings],
    applicationForms: [...guild2ApplicationForms],
    applicationTemplates: [...guild2ApplicationTemplates],
    applicationSubmissions: [...guild2ApplicationSubmissions],
    wowGuildNews: [...guild2WowGuildNews],
    craftingBoard: null,
    craftingMappings: [],
    craftingOrders: [],
    leaveMessages: { ...guild2LeaveMessages },
    autoKicker: { ...guild2AutoKicker },
    language: { ...guild2Language },
  },
  // Support-mode guild — data is readable but writes are denied at resolver level
  "999000000000000003": {
    modRoles: [...guild3ModRoles],
    autoDelete: [...guild3AutoDelete],
    reminders: [...guild3Reminders],
    reactionRoles: [],
    roleMappings: [],
    applicationForms: [],
    applicationTemplates: [],
    applicationSubmissions: [],
    wowGuildNews: [],
    craftingBoard: null,
    craftingMappings: [],
    craftingOrders: [],
    leaveMessages: { ...guild3LeaveMessages },
    autoKicker: { ...guild3AutoKicker },
    language: { ...guild3Language },
  },
};

let mutablePremiumUsers = [...operatorPremiumUsers];

// ── Route table ───────────────────────────────────────────────────────────────

// Fixed-length tuple so destructuring gives `string` (not `string | undefined`)
// even with noUncheckedIndexedAccess.  The max regex capture depth in this file
// is 3 (full-match + 3 groups), so 5 elements is enough with spare room.
type Caps = [string, string, string, string, string];

type Handler = (
  method: string,
  match: Caps,
  body: unknown,
) => { data: unknown; supportMode: boolean };

interface Route {
  pattern: RegExp;
  handler: Handler;
}

function ok(data: unknown, supportMode = false) {
  return { data, supportMode };
}

function guildStore(guildId: string, key: string): unknown[] {
  return (stores[guildId]?.[key] as unknown[]) ?? [];
}

const routes: Route[] = [
  // ── Channels & roles (Discord entity pickers) ─────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/channels$/,
    handler: (_m, _g) => ok(CHANNELS),
  },
  {
    pattern: /^\/guilds\/(\d+)\/discord\/roles$/,
    handler: (_m, _g) => ok({ roles: ROLES }),
  },
  // Legacy /roles path (used by some tabs)
  {
    pattern: /^\/guilds\/(\d+)\/roles$/,
    handler: (_m, _g) => ok(ROLES),
  },

  // ── Language ──────────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/language$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "PUT" && body) {
        const s = stores[guildId]!;
        s["language"] = { ...(s["language"] as object), ...(body as object) };
      }
      return ok(stores[guildId]?.["language"]);
    },
  },

  // ── Moderator roles ───────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/moderator-roles$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const roles = guildStore(guildId, "modRoles") as { guild_id: string; role_id: string }[];
        roles.push({ guild_id: guildId, ...(body as { role_id: string }) });
      }
      return ok(guildStore(guildId, "modRoles"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/moderator-roles\/(.+)$/,
    handler: (_m, [, guildId, roleId]) => {
      if (_m === "DELETE") {
        const roles = guildStore(guildId, "modRoles") as { role_id: string }[];
        stores[guildId]!["modRoles"] = roles.filter((r) => r.role_id !== roleId);
      }
      return ok(undefined);
    },
  },

  // ── Leave messages ────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/leave-messages$/,
    handler: (_m, [, guildId], body) => {
      if ((_m === "PUT" || _m === "PATCH") && body) {
        const s = stores[guildId]!;
        s["leaveMessages"] = { ...(s["leaveMessages"] as object), ...(body as object) };
      }
      return ok(stores[guildId]?.["leaveMessages"]);
    },
  },

  // ── Auto delete ───────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/auto-delete$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const rules = guildStore(guildId, "autoDelete") as unknown[];
        rules.push({ id: nextId(), guild_id: guildId, ...(body as object) });
      }
      return ok(guildStore(guildId, "autoDelete"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/auto-delete\/(\d+)$/,
    handler: (_m, [, guildId, ruleId], body) => {
      if (_m === "PATCH" && body) {
        const rules = guildStore(guildId, "autoDelete") as { id: number }[];
        const idx = rules.findIndex((r) => r.id === Number(ruleId));
        if (idx >= 0) rules[idx] = { ...rules[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["autoDelete"] = (guildStore(guildId, "autoDelete") as { id: number }[]).filter(
          (r) => r.id !== Number(ruleId),
        );
      }
      return ok(undefined);
    },
  },

  // ── Auto kicker ───────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/auto-kicker$/,
    handler: (_m, [, guildId], body) => {
      if ((_m === "PUT" || _m === "PATCH") && body) {
        const s = stores[guildId]!;
        s["autoKicker"] = { ...(s["autoKicker"] as object), ...(body as object) };
      }
      return ok(stores[guildId]?.["autoKicker"]);
    },
  },

  // ── Reminders ─────────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/reminders$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const reminders = guildStore(guildId, "reminders") as unknown[];
        reminders.push({
          id: nextId(),
          channel_name: null,
          author: "TestOperator",
          enabled: true,
          next_fire: new Date(Date.now() + 3600000).toISOString(),
          count: 0,
          ...(body as object),
        });
      }
      return ok(guildStore(guildId, "reminders"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/reminders\/(\d+)$/,
    handler: (_m, [, guildId, remId], body) => {
      if (_m === "PATCH" && body) {
        const reminders = guildStore(guildId, "reminders") as { id: number }[];
        const idx = reminders.findIndex((r) => r.id === Number(remId));
        if (idx >= 0) reminders[idx] = { ...reminders[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["reminders"] = (guildStore(guildId, "reminders") as { id: number }[]).filter(
          (r) => r.id !== Number(remId),
        );
      }
      return ok(undefined);
    },
  },

  // ── Reaction roles ────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/reaction-roles$/,
    handler: (_m, [, guildId]) => ok(guildStore(guildId, "reactionRoles")),
  },

  // ── Role mappings ─────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/role-mappings$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const mappings = guildStore(guildId, "roleMappings") as unknown[];
        mappings.push({ id: nextId(), guild_id: guildId, ...(body as object) });
      }
      return ok(guildStore(guildId, "roleMappings"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/role-mappings\/(\d+)$/,
    handler: (_m, [, guildId, mapId]) => {
      if (_m === "DELETE") {
        stores[guildId]!["roleMappings"] = (guildStore(guildId, "roleMappings") as { id: number }[]).filter(
          (r) => r.id !== Number(mapId),
        );
      }
      return ok(undefined);
    },
  },

  // ── Application forms ─────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/application-forms$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const forms = guildStore(guildId, "applicationForms") as unknown[];
        forms.push({ id: nextId(), questions: [], required_approvals: 1, required_denials: 1, ...(body as object) });
      }
      return ok(guildStore(guildId, "applicationForms"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-forms\/(\d+)\/questions$/,
    handler: (_m, [, guildId, formId], body) => {
      const forms = guildStore(guildId, "applicationForms") as { id: number; questions: unknown[] }[];
      const form = forms.find((f) => f.id === Number(formId));
      if (_m === "POST" && body && form) {
        form.questions.push({ id: nextId(), sort_order: form.questions.length + 1, ...(body as object) });
      }
      return ok(form?.questions ?? []);
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-forms\/(\d+)\/questions\/(\d+)$/,
    handler: (_m, [, guildId, formId, qId], body) => {
      const forms = guildStore(guildId, "applicationForms") as { id: number; questions: { id: number }[] }[];
      const form = forms.find((f) => f.id === Number(formId));
      if (_m === "PATCH" && body && form) {
        const idx = form.questions.findIndex((q) => q.id === Number(qId));
        if (idx >= 0) form.questions[idx] = { ...form.questions[idx]!, ...(body as object) };
      }
      if (_m === "DELETE" && form) {
        form.questions = form.questions.filter((q) => q.id !== Number(qId));
      }
      return ok(undefined);
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-forms\/(\d+)$/,
    handler: (_m, [, guildId, formId], body) => {
      const forms = guildStore(guildId, "applicationForms") as { id: number }[];
      if (_m === "PATCH" && body) {
        const idx = forms.findIndex((f) => f.id === Number(formId));
        if (idx >= 0) forms[idx] = { ...forms[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["applicationForms"] = forms.filter((f) => f.id !== Number(formId));
      }
      return ok(undefined);
    },
  },

  // ── Application templates ─────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/application-templates$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const templates = guildStore(guildId, "applicationTemplates") as unknown[];
        templates.push({ id: nextId(), is_built_in: false, questions: [], ...(body as object) });
      }
      return ok(guildStore(guildId, "applicationTemplates"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-templates\/(\d+)\/questions$/,
    handler: (_m, [, guildId, tplId], body) => {
      const templates = guildStore(guildId, "applicationTemplates") as { id: number; questions: unknown[] }[];
      const tpl = templates.find((t) => t.id === Number(tplId));
      if (_m === "POST" && body && tpl) {
        tpl.questions.push({ id: nextId(), sort_order: tpl.questions.length + 1, ...(body as object) });
      }
      return ok(tpl?.questions ?? []);
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-templates\/(\d+)\/questions\/(\d+)$/,
    handler: (_m, [, guildId, tplId, qId], body) => {
      const templates = guildStore(guildId, "applicationTemplates") as { id: number; questions: { id: number }[] }[];
      const tpl = templates.find((t) => t.id === Number(tplId));
      if (_m === "DELETE" && tpl) {
        tpl.questions = tpl.questions.filter((q) => q.id !== Number(qId));
      }
      if (_m === "PATCH" && body && tpl) {
        const idx = tpl.questions.findIndex((q) => q.id === Number(qId));
        if (idx >= 0) tpl.questions[idx] = { ...tpl.questions[idx]!, ...(body as object) };
      }
      return ok(undefined);
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-templates\/(\d+)$/,
    handler: (_m, [, guildId, tplId], body) => {
      const templates = guildStore(guildId, "applicationTemplates") as { id: number }[];
      if (_m === "PATCH" && body) {
        const idx = templates.findIndex((t) => t.id === Number(tplId));
        if (idx >= 0) templates[idx] = { ...templates[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["applicationTemplates"] = templates.filter((t) => t.id !== Number(tplId));
      }
      return ok(undefined);
    },
  },

  // ── Application submissions ───────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/application-submissions$/,
    handler: (_m, [, guildId]) => ok(guildStore(guildId, "applicationSubmissions")),
  },
  {
    pattern: /^\/guilds\/(\d+)\/application-submissions\/(\d+)\/decide$/,
    handler: (_m, [, guildId, subId], body) => {
      const subs = guildStore(guildId, "applicationSubmissions") as { id: number; status: string; decision_reason: string | null }[];
      const sub = subs.find((s) => s.id === Number(subId));
      if (sub && body) {
        const { decision, reason } = body as { decision: string; reason?: string };
        sub.status = decision;
        sub.decision_reason = reason ?? null;
      }
      return ok(sub);
    },
  },

  // ── WoW (shared endpoint — returns both guild_news and crafting_boards) ───
  {
    pattern: /^\/guilds\/(\d+)\/wow$/,
    handler: (_m, [, guildId]) => {
      const news = guildStore(guildId, "wowGuildNews");
      const board = stores[guildId]?.["craftingBoard"];
      return ok({
        guild_news: news,
        crafting_boards: board ? [board] : [],
      });
    },
  },

  // ── WoW guild news configs ────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/wow\/news-configs$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const trackers = guildStore(guildId, "wowGuildNews") as unknown[];
        trackers.push({ id: nextId(), enabled: true, last_activity: null, tracked_characters: 0, min_level: 10, active_days: 7, ...(body as object) });
      }
      return ok(guildStore(guildId, "wowGuildNews"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/wow\/news-configs\/(\d+)\/roster$/,
    handler: () => ok([]),
  },
  {
    pattern: /^\/guilds\/(\d+)\/wow\/news-configs\/(\d+)$/,
    handler: (_m, [, guildId, newsId], body) => {
      const trackers = guildStore(guildId, "wowGuildNews") as { id: number }[];
      if (_m === "PATCH" && body) {
        const idx = trackers.findIndex((t) => t.id === Number(newsId));
        if (idx >= 0) trackers[idx] = { ...trackers[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["wowGuildNews"] = trackers.filter((t) => t.id !== Number(newsId));
      }
      return ok(undefined);
    },
  },

  // ── WoW crafting ──────────────────────────────────────────────────────────
  {
    pattern: /^\/guilds\/(\d+)\/wow\/crafting-role-mappings$/,
    handler: (_m, [, guildId], body) => {
      if (_m === "POST" && body) {
        const mappings = guildStore(guildId, "craftingMappings") as unknown[];
        mappings.push({ id: nextId(), profession_name: "Unknown", ...(body as object) });
      }
      return ok(guildStore(guildId, "craftingMappings"));
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/wow\/crafting-role-mappings\/(\d+)$/,
    handler: (_m, [, guildId, mapId], body) => {
      if (_m === "PUT" && body) {
        const mappings = guildStore(guildId, "craftingMappings") as { id: number }[];
        const idx = mappings.findIndex((m) => m.id === Number(mapId));
        if (idx >= 0) mappings[idx] = { ...mappings[idx]!, ...(body as object) };
      }
      if (_m === "DELETE") {
        stores[guildId]!["craftingMappings"] = (guildStore(guildId, "craftingMappings") as { id: number }[]).filter(
          (m) => m.id !== Number(mapId),
        );
      }
      return ok(undefined);
    },
  },
  {
    pattern: /^\/guilds\/(\d+)\/wow\/crafting-orders$/,
    handler: (_m, [, guildId]) => ok(guildStore(guildId, "craftingOrders")),
  },

  // ── Operator ──────────────────────────────────────────────────────────────
  {
    pattern: /^\/operator\/health$/,
    handler: () => ok(operatorHealth),
  },
  {
    pattern: /^\/operator\/modules$/,
    handler: () => ok(operatorModules),
  },
  {
    pattern: /^\/operator\/modules\/[^/]+\/(load|unload)$/,
    handler: (_m, _g, body) => ok({ ...(body as object), success: true, error: null }),
  },
  {
    pattern: /^\/operator\/guilds$/,
    handler: () => ok({ guilds: operatorBotGuilds }),
  },
  {
    pattern: /^\/operator\/guilds\/999000000000000003$/,
    handler: () => ok(guild3Info, false),
  },
  {
    pattern: /^\/operator\/premium-users$/,
    handler: (_m, _g, body) => {
      if (_m === "POST" && body) {
        mutablePremiumUsers.push({
          user_id: (body as { user_id: string }).user_id,
          granted_at: new Date().toISOString(),
          granted_by: "999000000000000000",
        });
      }
      return ok(mutablePremiumUsers);
    },
  },
  {
    pattern: /^\/operator\/premium-users\/(.+)$/,
    handler: (_m, [, userId]) => {
      if (_m === "DELETE") {
        mutablePremiumUsers = mutablePremiumUsers.filter((u) => u.user_id !== userId);
      }
      return ok(undefined);
    },
  },
  {
    pattern: /^\/operator\/support$/,
    handler: () => ok({ success: true, sent_to: 1 }),
  },
];

// ── Public resolver ───────────────────────────────────────────────────────────

const SUPPORT_GUILD_ID = "999000000000000003";

export async function resolveTestRequest(
  method: string,
  path: string,
  body?: unknown,
): Promise<{ data: unknown; supportMode: boolean }> {
  // Strip query string before matching
  const pathOnly = path.split("?")[0]!;
  const isSupport = pathOnly.includes(SUPPORT_GUILD_ID);

  // Deny all writes to the support-mode guild (mirrors backend 403 behaviour)
  if (isSupport && method !== "GET") {
    throw Object.assign(new Error("Support mode — write access denied"), { status: 403 });
  }

  for (const route of routes) {
    const match = pathOnly.match(route.pattern);
    if (match) {
      const result = route.handler(method, match as unknown as Caps, body);
      // Elevate supportMode flag for every response from the support guild
      return isSupport ? { ...result, supportMode: true } : result;
    }
  }
  // Unmatched path: return empty success
  return { data: null, supportMode: false };
}
