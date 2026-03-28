# -*- coding: utf-8 -*-
"""Application domain models — re-exported from submodules for backward-compatible imports."""

from models.application.config import ApplicationGuildConfig, ApplicationGuildRole
from models.application.forms import (
    ApplicationForm,
    ApplicationQuestion,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    TEMPLATE_KEY_MAP,
)
from models.application.submissions import (
    BUILT_IN_TEMPLATES,
    ApplicationAnswer,
    ApplicationSubmission,
    ApplicationVote,
    SubmissionStatus,
    VoteType,
    seed_built_in_templates,
)

__all__ = [
    "ApplicationGuildConfig",
    "ApplicationGuildRole",
    "ApplicationForm",
    "ApplicationQuestion",
    "ApplicationTemplate",
    "ApplicationTemplateQuestion",
    "BUILT_IN_TEMPLATES",
    "TEMPLATE_KEY_MAP",
    "ApplicationAnswer",
    "ApplicationSubmission",
    "ApplicationVote",
    "SubmissionStatus",
    "VoteType",
    "seed_built_in_templates",
]
