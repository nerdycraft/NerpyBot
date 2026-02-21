# -*- coding: utf-8 -*-

from discord.app_commands import CheckFailure


class NerpyException(Exception):
    pass


class NerpyInfraException(NerpyException):
    """Infrastructure error (DB failure, external API failure, etc.).

    Treated like NerpyException for user-facing messages, but also triggers
    an operator DM notification so the bot owner is aware without waiting for
    a user report.  Raise with ``from original_exc`` to include the full
    chained traceback in the DM.
    """

    pass


class SilentCheckFailure(CheckFailure):
    """A check already sent its own rejection message — the error handler should not send another."""

    pass
