# -*- coding: utf-8 -*-
"""Tests for the NerpyBot exception hierarchy."""

from discord.app_commands import CheckFailure
from utils.errors import (
    NerpyException,
    NerpyInfraException,
    NerpyNotFoundError,
    NerpyPermissionError,
    NerpyUserException,
    NerpyValidationError,
    SilentCheckFailure,
)


def test_user_exception_is_nerpy_exception():
    assert issubclass(NerpyUserException, NerpyException)


def test_not_found_is_user_exception():
    assert issubclass(NerpyNotFoundError, NerpyUserException)


def test_validation_is_user_exception():
    assert issubclass(NerpyValidationError, NerpyUserException)


def test_permission_is_user_exception():
    assert issubclass(NerpyPermissionError, NerpyUserException)


def test_infra_is_nerpy_exception():
    assert issubclass(NerpyInfraException, NerpyException)


def test_infra_is_not_user_exception():
    assert not issubclass(NerpyInfraException, NerpyUserException)


def test_silent_check_failure_unchanged():
    assert issubclass(SilentCheckFailure, CheckFailure)
