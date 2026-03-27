# -*- coding: utf-8 -*-
"""WoW domain models — re-exported from submodules for backward-compatible imports."""

from models.wow.characters import WowCharacterMounts
from models.wow.crafting import (
    BIND_ON_ACQUIRE,
    BIND_ON_EQUIP,
    BIND_TO_ACCOUNT,
    CURRENT_BOARD_VERSION,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_OPEN,
    RECIPE_TYPE_CRAFTED,
    RECIPE_TYPE_HOUSING,
    CraftingBoardConfig,
    CraftingOrder,
    CraftingRecipeCache,
    CraftingRoleMapping,
    _recipe_cache,  # noqa: F401 — re-exported for tests that monkeypatch this name
    _recipe_cache_generation,  # noqa: F401
    _recipe_cache_lock,  # noqa: F401
    invalidate_recipe_cache,
)
from models.wow.guild import WoW, WowGuildNewsConfig

__all__ = [
    "BIND_ON_ACQUIRE",
    "BIND_ON_EQUIP",
    "BIND_TO_ACCOUNT",
    "CURRENT_BOARD_VERSION",
    "ORDER_STATUS_CANCELLED",
    "ORDER_STATUS_COMPLETED",
    "ORDER_STATUS_IN_PROGRESS",
    "ORDER_STATUS_OPEN",
    "RECIPE_TYPE_CRAFTED",
    "RECIPE_TYPE_HOUSING",
    "CraftingBoardConfig",
    "CraftingOrder",
    "CraftingRecipeCache",
    "CraftingRoleMapping",
    "invalidate_recipe_cache",
    "WoW",
    "WowCharacterMounts",
    "WowGuildNewsConfig",
]
