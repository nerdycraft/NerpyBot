"""Operator routes — module management, health."""

from fastapi import APIRouter

router = APIRouter(prefix="/operator", tags=["operator"])
