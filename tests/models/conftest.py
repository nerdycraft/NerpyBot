"""Fixtures shared across model tests."""

import pytest


@pytest.fixture(autouse=True)
def clear_recipe_cache():
    """Clear the CraftingRecipeCache TTL cache before each test.

    The cache is a module-level singleton that survives across tests.
    Tests use a per-test db_session whose rollback() expires all ORM
    objects — a subsequent test that hits the warm cache gets expired+
    detached instances and raises DetachedInstanceError. Clearing before
    each test keeps each test independent.
    """
    from models.wow import invalidate_recipe_cache

    invalidate_recipe_cache()
    yield
