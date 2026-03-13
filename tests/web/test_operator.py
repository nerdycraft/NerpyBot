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
