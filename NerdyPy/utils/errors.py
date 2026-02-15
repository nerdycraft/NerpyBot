# -*- coding: utf-8 -*-

from discord.ext.commands import CheckFailure


class NerpyException(Exception):
    pass


class SilentCheckFailure(CheckFailure):
    """A check already sent its own rejection message — the error handler should not send another."""

    pass
