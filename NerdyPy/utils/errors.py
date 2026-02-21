# -*- coding: utf-8 -*-

from discord.app_commands import CheckFailure


class NerpyException(Exception):
    """Base for all NerpyBot exceptions. Raiseable as a fallback."""

    pass


class NerpyUserException(NerpyException):
    """User-facing error — shown to the Discord user as-is."""

    pass


class NerpyNotFoundError(NerpyUserException):
    """A requested entity (tag, character, guild, realm) does not exist."""

    pass


class NerpyValidationError(NerpyUserException):
    """Input or state is invalid (bad parameter, missing placeholder, duplicate config)."""

    pass


class NerpyPermissionError(NerpyUserException):
    """The user or guild lacks a required role, or the bot lacks channel permissions."""

    pass


class NerpyInfraException(NerpyException):
    """Infrastructure failure — triggers an operator DM notification.

    Covers: DB errors, external API failures, Discord API failures, misconfiguration.
    Raise with ``from original_exc`` to chain the full traceback into the DM.
    """

    pass


class SilentCheckFailure(CheckFailure):
    """A check already sent its own rejection message — the error handler should not send another."""

    pass
