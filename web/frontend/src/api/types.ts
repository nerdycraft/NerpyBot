// TypeScript interfaces mirroring web/schemas.py Pydantic models.
// Field names are snake_case to match FastAPI's default JSON serialization.

// ── Auth ──

export interface GuildSummary {
  id: string;
  name: string;
  icon: string | null;
  permission_level: "admin" | "mod" | "member";
  bot_present: boolean;
  invite_url: string | null;
}

export interface UserInfo {
  id: string;
  username: string;
  is_operator: boolean;
  guilds: GuildSummary[];
}

// ── Guild Language ──

export interface LanguageConfig {
  guild_id: string;
  language: string;
}

export interface LanguageUpdate {
  language: string;
}

// ── Moderator Roles ──

export interface ModeratorRole {
  guild_id: string;
  role_id: string;
}

export interface ModeratorRoleCreate {
  role_id: string;
}

// ── Leave Messages ──

export interface LeaveMessageConfig {
  guild_id: string;
  channel_id: string | null;
  message: string | null;
  enabled: boolean;
}

export interface LeaveMessageUpdate {
  channel_id?: string | null;
  message?: string | null;
  enabled?: boolean | null;
}

// ── Auto Delete ──

export interface AutoDeleteRule {
  id: number;
  guild_id: string;
  channel_id: string;
  keep_messages: number;
  delete_older_than: number;
  delete_pinned: boolean;
  enabled: boolean;
}

export interface AutoDeleteCreate {
  channel_id: string;
  keep_messages?: number;
  delete_older_than?: number;
  delete_pinned?: boolean;
  enabled?: boolean;
}

export interface AutoDeleteUpdate {
  keep_messages?: number | null;
  delete_older_than?: number | null;
  delete_pinned?: boolean | null;
  enabled?: boolean | null;
}

// ── Auto Kicker ──

export interface AutoKickerConfig {
  guild_id: string;
  kick_after: number;
  enabled: boolean;
  reminder_message: string | null;
}

export interface AutoKickerUpdate {
  kick_after?: number | null;
  enabled?: boolean | null;
  reminder_message?: string | null;
}

// ── Reaction Roles ──

export interface ReactionRoleEntrySchema {
  emoji: string;
  role_id: string;
}

export interface ReactionRoleMessageSchema {
  id: number;
  channel_id: string;
  message_id: string;
  entries: ReactionRoleEntrySchema[];
}

// ── Role Mappings ──

export interface RoleMappingSchema {
  id: number;
  guild_id: string;
  source_role_id: string;
  target_role_id: string;
}

export interface RoleMappingCreate {
  source_role_id: string;
  target_role_id: string;
}

// ── Reminders ──

export type ReminderScheduleType = "interval" | "daily" | "weekly" | "monthly";

export interface ReminderSchema {
  id: number;
  channel_id: string;
  channel_name: string | null;
  author: string | null;
  message: string | null;
  enabled: boolean;
  schedule_type: string;
  next_fire: string;
  count: number;
  interval_seconds: number | null;
  schedule_time: string | null;
  schedule_day_of_week: number | null;
  schedule_day_of_month: number | null;
  timezone: string | null;
}

export interface ReminderCreate {
  channel_id: string;
  message: string;
  schedule_type: ReminderScheduleType;
  interval_seconds?: number | null;
  schedule_time?: string | null;
  schedule_day_of_week?: number | null;
  schedule_day_of_month?: number | null;
  timezone?: string;
}

export interface ReminderUpdate {
  message?: string | null;
  enabled?: boolean | null;
  channel_id?: string | null;
}

// ── Application Forms ──

export interface ApplicationQuestionSchema {
  id: number;
  question_text: string;
  sort_order: number;
}

export interface ApplicationFormSchema {
  id: number;
  name: string;
  review_channel_id: string | null;
  required_approvals: number;
  required_denials: number;
  approval_message: string | null;
  denial_message: string | null;
  apply_channel_id: string | null;
  apply_description: string | null;
  questions: ApplicationQuestionSchema[];
}

export interface ApplicationAnswerSchema {
  question_id: number;
  question_text: string;
  answer_text: string;
}

export interface ApplicationVoteSchema {
  voter_id: string;
  voter_name: string | null;
  vote: "approve" | "deny";
}

export interface ApplicationSubmissionSchema {
  id: number;
  form_name: string | null;
  user_id: string;
  user_name: string | null;
  status: string;
  submitted_at: string;
  decision_reason: string | null;
  answers: ApplicationAnswerSchema[];
  votes: ApplicationVoteSchema[];
}

export interface ApplicationTemplateQuestionSchema {
  id: number;
  question_text: string;
  sort_order: number;
}

export interface ApplicationTemplateSchema {
  id: number;
  name: string;
  is_built_in: boolean;
  approval_message: string | null;
  denial_message: string | null;
  questions: ApplicationTemplateQuestionSchema[];
}

// ── WoW ──

export interface WowGuildNewsSchema {
  id: number;
  channel_id: string;
  wow_guild_name: string;
  wow_realm_slug: string;
  region: string;
  enabled: boolean;
}

export interface CraftingBoardSchema {
  id: number;
  channel_id: string;
  description: string | null;
}

export interface CraftingRoleMappingSchema {
  id: number;
  role_id: string;
  profession_id: number;
  profession_name: string;
}

export interface CraftingRoleMappingCreate {
  role_id: string;
  profession_id: number;
}

export interface CraftingRoleMappingUpdate {
  profession_id: number;
}

export interface CraftingOrderSchema {
  id: number;
  item_name: string;
  icon_url: string | null;
  notes: string | null;
  status: string;
  creator_id: string;
  creator_name: string | null;
  crafter_id: string | null;
  crafter_name: string | null;
  create_date: string;
}

// ── Discord entities (for pickers) ──

export interface DiscordChannel {
  id: string;
  name: string;
  type: number;
}

export interface DiscordRole {
  id: string;
  name: string;
}

// ── Operator ──

export interface HealthResponse {
  status: string;
  uptime_seconds: number | null;
  latency_ms: number | null;
  guild_count: number | null;
  voice_connections: number | null;
  active_reminders: number | null;
  error_count_24h: number | null;
  python_version: string | null;
  discord_py_version: string | null;
  bot_version: string | null;
}

export interface ModuleInfo {
  name: string;
  loaded: boolean;
}

export interface ModuleListResponse {
  modules: Record<string, unknown>[];
  status: string;
}

export interface ModuleActionResponse {
  module: string;
  action: string;
  success: boolean;
  error: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
