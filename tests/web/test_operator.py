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

    def test_list_guilds_returns_empty_when_bot_unreachable(self, client, operator_header, monkeypatch):
        """list_guilds returns empty guilds list when bot is unreachable."""

        async def mock_send_bot_command(self, command, payload):
            return None

        from web.cache import ValkeyClient

        monkeypatch.setattr(ValkeyClient, "send_bot_command", mock_send_bot_command)

        response = client.get("/api/operator/guilds", headers=operator_header)
        assert response.status_code == 200
        data = response.json()
        assert data["guilds"] == []
