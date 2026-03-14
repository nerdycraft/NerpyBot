/**
 * Fixture data for test mode.  Typed against api/types.ts interfaces.
 *
 * All IDs use the 999000000000000xxx range so they're clearly synthetic and
 * will never collide with real Discord snowflakes.
 */

import type {
  AutoDeleteRule,
  AutoKickerConfig,
  BotGuildInfo,
  CraftingBoardSchema,
  CraftingOrderSchema,
  CraftingRoleMappingSchema,
  ApplicationFormSchema,
  ApplicationSubmissionSchema,
  ApplicationTemplateSchema,
  DiscordChannel,
  DiscordRole,
  HealthResponse,
  LanguageConfig,
  LeaveMessageConfig,
  ModuleListResponse,
  ModeratorRole,
  ReactionRoleMessageSchema,
  ReminderSchema,
  RoleMappingSchema,
  WowGuildNewsSchema,
  PremiumUserSchema,
} from "@/api/types";

// ── Shared: channels and roles (used across all guilds) ──────────────────────

export const CHANNELS: DiscordChannel[] = [
  { id: "800000000000000001", name: "general", type: 0 },
  { id: "800000000000000002", name: "announcements", type: 0 },
  { id: "800000000000000003", name: "mod-log", type: 0 },
  { id: "800000000000000004", name: "bot-commands", type: 0 },
  { id: "800000000000000005", name: "welcome", type: 0 },
  { id: "800000000000000006", name: "crafting-orders", type: 0 },
];

export const ROLES: DiscordRole[] = [
  { id: "700000000000000001", name: "Admin" },
  { id: "700000000000000002", name: "Moderator" },
  { id: "700000000000000003", name: "Member" },
  { id: "700000000000000004", name: "Bot" },
  { id: "700000000000000005", name: "Muted" },
];

// ── Guild 1: Nerdcraft Central — full feature set ────────────────────────────

const GUILD1 = "999000000000000001";

export const guild1Language: LanguageConfig = {
  guild_id: GUILD1,
  language: "en",
};

export const guild1ModRoles: ModeratorRole[] = [
  { guild_id: GUILD1, role_id: "700000000000000001" },
  { guild_id: GUILD1, role_id: "700000000000000002" },
];

export const guild1LeaveMessages: LeaveMessageConfig = {
  guild_id: GUILD1,
  channel_id: "800000000000000003",
  message: "Goodbye, {user}! We hope to see you again.",
  enabled: true,
};

export const guild1AutoDelete: AutoDeleteRule[] = [
  {
    id: 1,
    guild_id: GUILD1,
    channel_id: "800000000000000004",
    keep_messages: 100,
    delete_older_than: 7,
    delete_pinned: false,
    enabled: true,
  },
  {
    id: 2,
    guild_id: GUILD1,
    channel_id: "800000000000000001",
    keep_messages: 500,
    delete_older_than: 30,
    delete_pinned: true,
    enabled: false,
  },
];

export const guild1AutoKicker: AutoKickerConfig = {
  guild_id: GUILD1,
  kick_after: 7,
  enabled: true,
  reminder_message: "Hey {user}, you still haven't verified! You have 24 hours.",
};

export const guild1Reminders: ReminderSchema[] = [
  {
    id: 1,
    channel_id: "800000000000000004",
    channel_name: "bot-commands",
    author: "TestOperator",
    message: "Daily standup in 15 minutes!",
    enabled: true,
    schedule_type: "daily",
    next_fire: "2026-03-15T09:00:00Z",
    count: 42,
    schedule_time: "09:00",
    timezone: "Europe/Berlin",
    interval_seconds: null,
    schedule_day_of_week: null,
    schedule_day_of_month: null,
  },
  {
    id: 2,
    channel_id: "800000000000000001",
    channel_name: "general",
    author: "TestOperator",
    message: "Weekly raid night tonight at 20:00 server time!",
    enabled: true,
    schedule_type: "weekly",
    next_fire: "2026-03-16T18:00:00Z",
    count: 12,
    schedule_time: "18:00",
    schedule_day_of_week: 0,
    timezone: "UTC",
    interval_seconds: null,
    schedule_day_of_month: null,
  },
  {
    id: 3,
    channel_id: "800000000000000004",
    channel_name: "bot-commands",
    author: "TestOperator",
    message: "Server maintenance window starts soon.",
    enabled: false,
    schedule_type: "interval",
    next_fire: "2026-03-14T12:00:00Z",
    count: 7,
    interval_seconds: 3600,
    timezone: "UTC",
    schedule_time: null,
    schedule_day_of_week: null,
    schedule_day_of_month: null,
  },
];

export const guild1ReactionRoles: ReactionRoleMessageSchema[] = [
  {
    id: 1,
    channel_id: "800000000000000002",
    message_id: "888000000000000001",
    entries: [
      { emoji: "⚔️", role_id: "700000000000000001" },
      { emoji: "🛡️", role_id: "700000000000000002" },
      { emoji: "🧙", role_id: "700000000000000003" },
    ],
  },
];

export const guild1RoleMappings: RoleMappingSchema[] = [
  {
    id: 1,
    guild_id: GUILD1,
    source_role_id: "700000000000000002",
    target_role_id: "700000000000000005",
  },
  {
    id: 2,
    guild_id: GUILD1,
    source_role_id: "700000000000000001",
    target_role_id: "700000000000000003",
  },
];

export const guild1ApplicationForms: ApplicationFormSchema[] = [
  {
    id: 1,
    name: "Guild Membership Application",
    review_channel_id: "800000000000000003",
    required_approvals: 2,
    required_denials: 1,
    approval_message: "Welcome to Nerdcraft Central! Please read #rules.",
    denial_message: "Thanks for applying, but we're not accepting new members right now.",
    apply_channel_id: "800000000000000004",
    apply_description: "Fill out this form to apply for guild membership.",
    questions: [
      { id: 1, question_text: "Tell us about yourself.", sort_order: 1 },
      { id: 2, question_text: "What games do you play?", sort_order: 2 },
      { id: 3, question_text: "How did you find us?", sort_order: 3 },
    ],
  },
];

export const guild1ApplicationTemplates: ApplicationTemplateSchema[] = [
  {
    id: 1,
    name: "Standard Membership",
    is_built_in: false,
    approval_message: "You've been accepted!",
    denial_message: "Your application was denied.",
    questions: [
      { id: 1, question_text: "Tell us about yourself.", sort_order: 1 },
      { id: 2, question_text: "What are you looking for in a community?", sort_order: 2 },
    ],
  },
];

export const guild1ApplicationSubmissions: ApplicationSubmissionSchema[] = [
  {
    id: 1,
    form_name: "Guild Membership Application",
    user_id: "111000000000000001",
    user_name: "DragonSlayer99",
    status: "pending",
    submitted_at: "2026-03-13T14:22:00Z",
    decision_reason: null,
    answers: [
      { question_id: 1, question_text: "Tell us about yourself.", answer_text: "Hi! I'm a veteran MMO player looking for a chill guild." },
      { question_id: 2, question_text: "What games do you play?", answer_text: "WoW, FFXIV, and some indie games." },
      { question_id: 3, question_text: "How did you find us?", answer_text: "A friend recommended you." },
    ],
    votes: [{ voter_id: "999000000000000000", voter_name: "TestOperator", vote: "approve" }],
  },
  {
    id: 2,
    form_name: "Guild Membership Application",
    user_id: "111000000000000002",
    user_name: "StargazerX",
    status: "approved",
    submitted_at: "2026-03-10T09:00:00Z",
    decision_reason: null,
    answers: [
      { question_id: 1, question_text: "Tell us about yourself.", answer_text: "I'm a casual player who loves community events." },
      { question_id: 2, question_text: "What games do you play?", answer_text: "WoW main, occasional Diablo." },
      { question_id: 3, question_text: "How did you find us?", answer_text: "Discord server listing." },
    ],
    votes: [
      { voter_id: "999000000000000000", voter_name: "TestOperator", vote: "approve" },
      { voter_id: "111000000000000099", voter_name: "OfficerOne", vote: "approve" },
    ],
  },
  {
    id: 3,
    form_name: "Guild Membership Application",
    user_id: "111000000000000003",
    user_name: "TrollHunter",
    status: "denied",
    submitted_at: "2026-03-08T16:45:00Z",
    decision_reason: "Prior conduct issues in other communities.",
    answers: [
      { question_id: 1, question_text: "Tell us about yourself.", answer_text: "Just looking for a guild." },
      { question_id: 2, question_text: "What games do you play?", answer_text: "WoW." },
      { question_id: 3, question_text: "How did you find us?", answer_text: "Reddit." },
    ],
    votes: [
      { voter_id: "999000000000000000", voter_name: "TestOperator", vote: "deny" },
      { voter_id: "111000000000000099", voter_name: "OfficerOne", vote: "deny" },
    ],
  },
];

export const guild1WowGuildNews: WowGuildNewsSchema[] = [
  {
    id: 1,
    channel_id: "800000000000000002",
    wow_guild_name: "Nerdcraft",
    wow_realm_slug: "draenor",
    region: "eu",
    enabled: true,
    min_level: 10,
    active_days: 7,
    last_activity: "2026-03-13T20:00:00Z",
    tracked_characters: 23,
  },
];

export const guild1CraftingBoard: CraftingBoardSchema = {
  id: 1,
  channel_id: "800000000000000006",
  description: "Post crafting requests here! React to claim an order.",
};

export const guild1CraftingMappings: CraftingRoleMappingSchema[] = [
  { id: 1, role_id: "700000000000000002", profession_id: 164, profession_name: "Blacksmithing" },
  { id: 2, role_id: "700000000000000003", profession_id: 171, profession_name: "Alchemy" },
];

export const guild1CraftingOrders: CraftingOrderSchema[] = [
  {
    id: 1,
    item_name: "Tempered Potion of Power",
    icon_url: null,
    notes: "Need 5x for raid on Sunday",
    status: "open",
    creator_id: "111000000000000001",
    creator_name: "DragonSlayer99",
    crafter_id: null,
    crafter_name: null,
    create_date: "2026-03-13T18:00:00Z",
  },
  {
    id: 2,
    item_name: "Weathered Harbinger Axe",
    icon_url: null,
    notes: null,
    status: "claimed",
    creator_id: "111000000000000002",
    creator_name: "StargazerX",
    crafter_id: "111000000000000099",
    crafter_name: "OfficerOne",
    create_date: "2026-03-12T10:30:00Z",
  },
  {
    id: 3,
    item_name: "Flask of Alchemical Chaos",
    icon_url: null,
    notes: "For progression night",
    status: "completed",
    creator_id: "111000000000000001",
    creator_name: "DragonSlayer99",
    crafter_id: "111000000000000099",
    crafter_name: "OfficerOne",
    create_date: "2026-03-10T09:00:00Z",
  },
];

// ── Guild 2: Quiet Corner — minimal guild ────────────────────────────────────

const GUILD2 = "999000000000000002";

export const guild2Language: LanguageConfig = {
  guild_id: GUILD2,
  language: "de",
};

export const guild2ModRoles: ModeratorRole[] = [];

export const guild2LeaveMessages: LeaveMessageConfig = {
  guild_id: GUILD2,
  channel_id: null,
  message: null,
  enabled: false,
};

export const guild2AutoDelete: AutoDeleteRule[] = [];

export const guild2AutoKicker: AutoKickerConfig = {
  guild_id: GUILD2,
  kick_after: 30,
  enabled: false,
  reminder_message: null,
};

export const guild2Reminders: ReminderSchema[] = [];
export const guild2ReactionRoles: ReactionRoleMessageSchema[] = [];
export const guild2RoleMappings: RoleMappingSchema[] = [];
export const guild2ApplicationForms: ApplicationFormSchema[] = [];
export const guild2ApplicationTemplates: ApplicationTemplateSchema[] = [];
export const guild2ApplicationSubmissions: ApplicationSubmissionSchema[] = [];
export const guild2WowGuildNews: WowGuildNewsSchema[] = [];

// ── Guild 3: External Server — support mode guild ────────────────────────────

const GUILD3 = "999000000000000003";

export const guild3Info: BotGuildInfo = {
  id: GUILD3,
  name: "External Server",
  icon: null,
  member_count: 412,
};

// ── Operator data ────────────────────────────────────────────────────────────

export const operatorHealth: HealthResponse = {
  status: "online",
  uptime_seconds: 172800,
  latency_ms: 42.5,
  guild_count: 4,
  voice_connections: 1,
  active_reminders: 3,
  error_count_24h: 2,
  memory_mb: 128.4,
  cpu_percent: 3.7,
  python_version: "3.14.0",
  discord_py_version: "2.4.0",
  bot_version: "0.6.0",
  voice_details: [
    {
      guild_id: GUILD1,
      guild_name: "Nerdcraft Central",
      channel_id: "800000000000000007",
      channel_name: "Voice General",
    },
  ],
};

export const operatorModules: ModuleListResponse = {
  modules: [
    { name: "admin", loaded: true, protected: true },
    { name: "application", loaded: true, protected: false },
    { name: "reminder", loaded: true, protected: false },
    { name: "wow", loaded: true, protected: false },
    { name: "reactionrole", loaded: true, protected: false },
    { name: "leavemsg", loaded: true, protected: false },
  ],
  available: ["league", "music"],
  status: "ok",
};

export const operatorBotGuilds: BotGuildInfo[] = [
  { id: GUILD1, name: "Nerdcraft Central", icon: null, member_count: 128 },
  { id: GUILD2, name: "Quiet Corner", icon: null, member_count: 15 },
  { id: GUILD3, name: "External Server", icon: null, member_count: 412 },
  { id: "999000000000000004", name: "Cool Guild", icon: null, member_count: 67 },
];

export const operatorPremiumUsers: PremiumUserSchema[] = [
  { user_id: "111000000000000001", granted_at: "2026-01-10T12:00:00Z", granted_by: "999000000000000000" },
  { user_id: "111000000000000002", granted_at: "2026-02-14T09:30:00Z", granted_by: "999000000000000000" },
];
