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
  required_approvals: number;
  required_denials: number;
  questions: ApplicationQuestionSchema[];
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
