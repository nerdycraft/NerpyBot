class TestAppFactory:
    def test_app_creates_successfully(self, client):
        """The app factory produces a working FastAPI app."""
        response = client.get("/api/docs")
        assert response.status_code == 200

    def test_health_requires_no_auth(self, client):
        """OpenAPI docs are accessible without auth."""
        response = client.get("/api/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "/api/auth/login" in str(data)
