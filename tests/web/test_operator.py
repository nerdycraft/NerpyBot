class TestHealthEndpoint:
    def test_health_requires_operator(self, client, auth_header):
        response = client.get("/api/operator/health", headers=auth_header)
        assert response.status_code == 403

    def test_health_returns_unreachable_when_no_bot(self, client, operator_header):
        response = client.get("/api/operator/health", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unreachable"
        assert data["memory_mb"] is None
        assert data["cpu_percent"] is None
        assert data["error_count_24h"] is None
        assert data["active_reminders"] is None
        assert data["voice_details"] == []


class TestModuleEndpoints:
    def test_list_modules_requires_operator(self, client, auth_header):
        response = client.get("/api/operator/modules", headers=auth_header)
        assert response.status_code == 403

    def test_load_module_requires_operator(self, client, auth_header):
        response = client.post("/api/operator/modules/music/load", headers=auth_header)
        assert response.status_code == 403

    def test_unload_module_requires_operator(self, client, auth_header):
        response = client.post("/api/operator/modules/music/unload", headers=auth_header)
        assert response.status_code == 403

    def test_load_module_returns_unreachable(self, client, operator_header):
        """Without a bot connected, module commands return failure."""
        response = client.post("/api/operator/modules/music/load", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestGuildListEndpoint:
    def test_list_guilds_requires_operator(self, client, auth_header):
        """Non-operators are rejected with 403."""
        response = client.get("/api/operator/guilds", headers=auth_header)
        assert response.status_code == 403

    def test_list_guilds_returns_guild_list(self, client, operator_header, monkeypatch):
        """list_guilds returns guilds when bot is reachable."""
        mock_result = {
            "guilds": [
                {"id": "111111", "name": "Guild One", "icon": "abc123", "member_count": 42},
                {"id": "222222", "name": "Guild Two", "icon": None, "member_count": 100},
            ]
        }

        async def mock_send_bot_command(self, command, payload):
            assert command == "list_guilds"
            return mock_result

        from web.cache import ValkeyClient

        monkeypatch.setattr(ValkeyClient, "send_bot_command", mock_send_bot_command)

        response = client.get("/api/operator/guilds", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data["guilds"]) == 2
        assert data["guilds"][0]["id"] == "111111"
        assert data["guilds"][0]["name"] == "Guild One"
        assert data["guilds"][0]["icon"] == "abc123"
        assert data["guilds"][0]["member_count"] == 42
        assert data["guilds"][1]["icon"] is None

    def test_list_guilds_returns_503_when_bot_unreachable(self, client, operator_header, monkeypatch):
        """list_guilds returns 503 when bot is unreachable (not an empty list)."""

        async def mock_send_bot_command(self, command, payload):
            assert command == "list_guilds"
            return None

        from web.cache import ValkeyClient

        monkeypatch.setattr(ValkeyClient, "send_bot_command", mock_send_bot_command)

        response = client.get("/api/operator/guilds", headers=operator_header)
        assert response.status_code == 503


class TestRecipeCacheBrowse:
    def test_browse_requires_operator(self, client, auth_header):
        response = client.get("/api/operator/recipe-cache", headers=auth_header)
        assert response.status_code == 403

    def test_browse_empty_cache(self, client, operator_header):
        response = client.get("/api/operator/recipe-cache", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["recipes"] == []
        assert data["professions"] == []
        assert data["expansions"] == []
        assert data["total"] == 0

    def test_browse_returns_cached_recipes(self, client, operator_header, web_db_session):
        from datetime import UTC, datetime
        from models.wow import CraftingRecipeCache

        r = CraftingRecipeCache(
            RecipeId=100,
            ProfessionId=164,
            ProfessionName="Blacksmithing",
            ItemId=200,
            ItemName="Tempered Helm",
            RecipeType="crafted",
            ItemClassName="Armor",
            ItemClassId=4,
            ItemSubClassName="Plate",
            ItemSubClassId=6,
            ExpansionName="Midnight",
            CategoryName="Helms",
            LastSynced=datetime.now(UTC),
        )
        web_db_session.add(r)
        web_db_session.commit()

        response = client.get("/api/operator/recipe-cache", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["recipes"]) == 1
        recipe = data["recipes"][0]
        assert recipe["recipe_id"] == 100
        assert recipe["item_name"] == "Tempered Helm"
        assert recipe["profession_name"] == "Blacksmithing"
        assert recipe["recipe_type"] == "crafted"
        assert recipe["wowhead_url"] == "https://www.wowhead.com/item=200"
        assert data["professions"] == [{"id": 164, "name": "Blacksmithing"}]
        assert data["expansions"] == ["Midnight"]

    def test_browse_filter_by_type(self, client, operator_header, web_db_session):
        from datetime import UTC, datetime
        from models.wow import CraftingRecipeCache

        web_db_session.add_all(
            [
                CraftingRecipeCache(
                    RecipeId=1,
                    ProfessionId=171,
                    ProfessionName="Alchemy",
                    ItemId=10,
                    ItemName="Flask",
                    RecipeType="crafted",
                    LastSynced=datetime.now(UTC),
                ),
                CraftingRecipeCache(
                    RecipeId=2,
                    ProfessionId=185,
                    ProfessionName="Cooking",
                    ItemId=20,
                    ItemName="Fancy Chair",
                    RecipeType="housing",
                    LastSynced=datetime.now(UTC),
                ),
            ]
        )
        web_db_session.commit()

        response = client.get("/api/operator/recipe-cache?recipe_type=housing", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["recipes"][0]["item_name"] == "Fancy Chair"
