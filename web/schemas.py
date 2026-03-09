"""Pydantic request/response models for the web API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── Auth ──


class UserInfo(BaseModel):
    id: str
    username: str
    is_operator: bool
    guilds: list[GuildSummary]


class GuildSummary(BaseModel):
    id: str
    name: str
    icon: str | None
    permission_level: Literal["admin", "mod", "member"]
    bot_present: bool = False
    invite_url: str | None = None


# ── Guild Language ──


class LanguageConfig(BaseModel):
    guild_id: str
    language: str


class LanguageUpdate(BaseModel):
    language: str


# ── Moderator Roles ──


class ModeratorRole(BaseModel):
    guild_id: str
    role_id: str


class ModeratorRoleCreate(BaseModel):
    role_id: str


# ── Leave Messages ──


class LeaveMessageConfig(BaseModel):
    guild_id: str
    channel_id: str | None
    message: str | None
    enabled: bool


class LeaveMessageUpdate(BaseModel):
    channel_id: str | None = None
    message: str | None = None
    enabled: bool | None = None


# ── Auto Delete ──


class AutoDeleteRule(BaseModel):
    id: int
    guild_id: str
    channel_id: str
    keep_messages: int
    delete_older_than: int
    delete_pinned: bool
    enabled: bool


class AutoDeleteCreate(BaseModel):
    channel_id: str
    keep_messages: int = Field(0, ge=0)
    delete_older_than: int = Field(0, ge=0)
    delete_pinned: bool = False
    enabled: bool = True


class AutoDeleteUpdate(BaseModel):
    keep_messages: int | None = Field(None, ge=0)
    delete_older_than: int | None = Field(None, ge=0)
    delete_pinned: bool | None = None
    enabled: bool | None = None


# ── Auto Kicker ──


class AutoKickerConfig(BaseModel):
    guild_id: str
    kick_after: int
    enabled: bool
    reminder_message: str | None


class AutoKickerUpdate(BaseModel):
    kick_after: int | None = None
    enabled: bool | None = None
    reminder_message: str | None = None


# ── Reaction Roles (read-only) ──


class ReactionRoleEntrySchema(BaseModel):
    emoji: str
    role_id: str


class ReactionRoleMessageSchema(BaseModel):
    id: int
    channel_id: str
    message_id: str
    entries: list[ReactionRoleEntrySchema]


# ── Role Mappings ──


class RoleMappingSchema(BaseModel):
    id: int
    guild_id: str
    source_role_id: str
    target_role_id: str


class RoleMappingCreate(BaseModel):
    source_role_id: str
    target_role_id: str


# ── Reminders (read-only) ──


class ReminderSchema(BaseModel):
    id: int
    channel_id: str
    channel_name: str | None
    author: str | None
    message: str | None
    enabled: bool
    schedule_type: str
    next_fire: str
    count: int


# ── Application Forms (read-only) ──


class ApplicationQuestionSchema(BaseModel):
    id: int
    question_text: str
    sort_order: int


class ApplicationFormSchema(BaseModel):
    id: int
    name: str
    required_approvals: int
    required_denials: int
    questions: list[ApplicationQuestionSchema]


# ── WoW (read-only) ──


class WowGuildNewsSchema(BaseModel):
    id: int
    channel_id: str
    wow_guild_name: str
    wow_realm_slug: str
    region: str
    enabled: bool


class CraftingBoardSchema(BaseModel):
    id: int
    channel_id: str
    description: str | None


# ── Operator ──


class HealthResponse(BaseModel):
    status: str  # "online" or "unreachable"
    uptime_seconds: float | None = None
    latency_ms: float | None = None
    guild_count: int | None = None
    voice_connections: int | None = None
    active_reminders: int | None = None  # Phase 3: populated once bot exposes it
    error_count_24h: int | None = None  # Phase 3: populated once error log is implemented
    python_version: str | None = None
    discord_py_version: str | None = None
    bot_version: str | None = None


class ModuleInfo(BaseModel):
    name: str
    loaded: bool


class ModuleListResponse(BaseModel):
    modules: list[dict]
    status: str = "ok"


class ModuleActionResponse(BaseModel):
    module: str
    action: str
    success: bool
    error: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
