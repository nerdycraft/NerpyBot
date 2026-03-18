"""Pydantic request/response models for the web API."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ── Auth ──


class UserInfo(BaseModel):
    id: str
    username: str
    is_operator: bool
    is_premium: bool
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


# ── Reminders ──


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
    interval_seconds: int | None = None
    schedule_time: str | None = None  # "HH:MM"
    schedule_day_of_week: int | None = None  # 0=Mon … 6=Sun
    schedule_day_of_month: int | None = None  # 1-28
    timezone: str | None = None


ReminderScheduleType = Literal["interval", "daily", "weekly", "monthly"]


class ReminderCreate(BaseModel):
    channel_id: str
    message: str
    schedule_type: ReminderScheduleType
    interval_seconds: Annotated[int, Field(ge=60)] | None = None
    schedule_time: str | None = None  # "HH:MM"
    schedule_day_of_week: Annotated[int, Field(ge=0, le=6)] | None = None
    schedule_day_of_month: Annotated[int, Field(ge=1, le=28)] | None = None
    timezone: str = "UTC"


class ReminderUpdate(BaseModel):
    message: str | None = None
    enabled: bool | None = None
    channel_id: str | None = None


# ── Application Forms ──


class ApplicationQuestionSchema(BaseModel):
    id: int
    question_text: str
    sort_order: int


class ApplicationFormSchema(BaseModel):
    id: int
    name: str
    review_channel_id: str | None = None
    required_approvals: int
    required_denials: int
    approval_message: str | None = None
    denial_message: str | None = None
    apply_channel_id: str | None = None
    apply_description: str | None = None
    questions: list[ApplicationQuestionSchema]


class ApplicationFormCreate(BaseModel):
    name: str
    required_approvals: int = Field(1, ge=1)
    required_denials: int = Field(1, ge=1)
    review_channel_id: str | None = None
    apply_channel_id: str | None = None
    approval_message: str | None = None
    denial_message: str | None = None
    apply_description: str | None = None


class ApplicationFormUpdate(BaseModel):
    name: str | None = None
    required_approvals: int | None = Field(None, ge=1)
    required_denials: int | None = Field(None, ge=1)
    review_channel_id: str | None = None
    apply_channel_id: str | None = None
    approval_message: str | None = None
    denial_message: str | None = None
    apply_description: str | None = None


class ApplicationQuestionCreate(BaseModel):
    question_text: str
    sort_order: int | None = None


class ApplicationQuestionUpdate(BaseModel):
    question_text: str | None = None
    sort_order: int | None = Field(None, ge=1)


class ApplicationAnswerSchema(BaseModel):
    question_id: int
    question_text: str
    answer_text: str


class ApplicationVoteSchema(BaseModel):
    voter_id: str
    voter_name: str | None
    vote: str


class ApplicationSubmissionSchema(BaseModel):
    id: int
    form_name: str | None = None
    user_id: str
    user_name: str | None
    status: str
    submitted_at: str
    decision_reason: str | None = None
    answers: list[ApplicationAnswerSchema]
    votes: list[ApplicationVoteSchema] = []


class ApplicationTemplateQuestionSchema(BaseModel):
    id: int
    question_text: str
    sort_order: int


class ApplicationTemplateSchema(BaseModel):
    id: int
    name: str
    is_built_in: bool
    approval_message: str | None = None
    denial_message: str | None = None
    questions: list[ApplicationTemplateQuestionSchema]


class ApplicationTemplateCreate(BaseModel):
    name: str
    approval_message: str | None = None
    denial_message: str | None = None
    question_texts: list[str] = []


class ApplicationTemplateUpdate(BaseModel):
    name: str | None = None
    approval_message: str | None = None
    denial_message: str | None = None


class ApplicationTemplateQuestionCreate(BaseModel):
    question_text: str


# ── WoW ──


class WowGuildNewsSchema(BaseModel):
    id: int
    channel_id: str
    wow_guild_name: str
    wow_realm_slug: str
    region: str
    enabled: bool
    min_level: int
    active_days: int
    last_activity: str | None = None
    tracked_characters: int = 0


class WowCharacterMountSchema(BaseModel):
    character_name: str
    realm_slug: str
    mount_count: int
    last_checked: str | None


class WowGuildNewsCreate(BaseModel):
    channel_id: str
    wow_guild_name: str
    wow_realm_slug: str
    region: str  # "eu" or "us"
    active_days: int = Field(7, ge=1)
    min_level: int = Field(10, ge=1)


class WowGuildNewsUpdate(BaseModel):
    channel_id: str | None = None
    active_days: int | None = Field(None, ge=1)
    min_level: int | None = Field(None, ge=1)
    enabled: bool | None = None


class CraftingBoardSchema(BaseModel):
    id: int
    channel_id: str
    description: str | None


class CraftingRoleMappingSchema(BaseModel):
    id: int
    role_id: str
    profession_id: int
    profession_name: str


class CraftingRoleMappingCreate(BaseModel):
    role_id: str
    profession_id: int


class CraftingRoleMappingUpdate(BaseModel):
    profession_id: int


class CraftingOrderSchema(BaseModel):
    id: int
    item_name: str
    icon_url: str | None = None
    notes: str | None = None
    status: str
    creator_id: str
    creator_name: str | None = None
    crafter_id: str | None = None
    crafter_name: str | None = None
    create_date: str


# ── Bot Guild List ──


class BotGuildInfo(BaseModel):
    id: str
    name: str
    icon: str | None
    member_count: int | None


class BotGuildListResponse(BaseModel):
    guilds: list[BotGuildInfo]


# ── Premium ──


class PremiumUserSchema(BaseModel):
    user_id: str
    granted_at: str
    granted_by: str | None


class PremiumUserGrant(BaseModel):
    user_id: str


# ── Operator ──


class VoiceConnectionDetail(BaseModel):
    guild_id: str
    guild_name: str
    channel_id: str
    channel_name: str


class HealthResponse(BaseModel):
    status: str  # "online" or "unreachable"
    uptime_seconds: float | None = None
    latency_ms: float | None = None
    guild_count: int | None = None
    voice_connections: int | None = None
    active_reminders: int | None = None
    error_count_24h: int | None = None
    memory_mb: float | None = None
    cpu_percent: float | None = None
    python_version: str | None = None
    discord_py_version: str | None = None
    bot_version: str | None = None
    voice_details: list[VoiceConnectionDetail] = []


class ModuleInfo(BaseModel):
    name: str
    loaded: bool
    protected: bool = False


class ModuleListResponse(BaseModel):
    modules: list[ModuleInfo]
    available: list[str] = []
    status: str = "ok"


class ModuleActionResponse(BaseModel):
    module: str
    action: str
    success: bool
    error: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Legal ──


class LegalContactResponse(BaseModel):
    enabled: bool
    name: str
    street: str
    zip_city: str
    country_en: str
    country_de: str
    email: str


# ── Support ──


class SupportMessageRequest(BaseModel):
    category: Literal["bug", "feature", "feedback", "other"]
    message: str = Field(..., min_length=10, max_length=2000)


class SupportMessageResponse(BaseModel):
    success: bool
    sent_to: int = 0


# ── Branding ──


class BrandingResponse(BaseModel):
    bot_name: str
    bot_description: str


# ── Bot permissions ──


class BotPermissionGuildResult(BaseModel):
    guild_id: str
    guild_name: str
    guild_icon: str | None
    missing: list[str]
    all_ok: bool


class BotPermissionsResponse(BaseModel):
    guilds: list[BotPermissionGuildResult]


class BotPermissionSubscription(BaseModel):
    guild_id: str
    subscribed: bool


# ── Error control ──


class ErrorStatusBucket(BaseModel):
    last_notified_ago: float
    suppressed_count: int


class ErrorStatusResponse(BaseModel):
    is_suppressed: bool
    suppressed_remaining: float | None
    throttle_window: int
    buckets: dict[str, ErrorStatusBucket]
    debug_enabled: bool | None = None


class ErrorSuppressRequest(BaseModel):
    duration: str = Field(..., description="Duration string, e.g. '30m', '2h', '1d'")


class ErrorActionResponse(BaseModel):
    success: bool
    seconds: int | None = None
    already_active: bool | None = None
    error: str | None = None


# ── Debug ──


class DebugToggleResponse(BaseModel):
    debug_enabled: bool


# ── Command sync ──


class SyncCommandsRequest(BaseModel):
    mode: Literal["global", "local", "copy", "clear"]
    guild_ids: list[str] = []


class SyncCommandsResponse(BaseModel):
    success: bool
    synced_count: int | None = None
    error: str | None = None


# ── Recipe sync ──


class RecipeSyncResponse(BaseModel):
    queued: bool
    error: str | None = None


class RecipeSyncStatusResponse(BaseModel):
    counts: dict[str, int]


class RecipeCacheEntry(BaseModel):
    recipe_id: int
    item_name: str
    profession_id: int
    profession_name: str
    recipe_type: str
    item_class_name: str | None
    item_subclass_name: str | None
    expansion_name: str | None
    category_name: str | None
    wowhead_url: str | None


class RecipeCacheProfession(BaseModel):
    id: int
    name: str


class RecipeCacheBrowseResponse(BaseModel):
    recipes: list[RecipeCacheEntry]
    professions: list[RecipeCacheProfession]
    expansions: list[str]
    total: int
