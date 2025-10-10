"""
Unit tests for FastAPI server

Following TDD: Write tests FIRST

Tests for:
- FastAPI app creation
- Router inclusion
- CORS middleware
- Exception handling
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.api.server import app


class TestFastAPIApp:
    """Test FastAPI application"""

    def test_app_is_fastapi_instance(self):
        """Should be a FastAPI instance"""
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_app_has_title(self):
        """Should have API title"""
        assert hasattr(app, "title")
        assert "LivChatSetup" in app.title

    def test_app_has_version(self):
        """Should have version"""
        assert hasattr(app, "version")
        assert app.version is not None

    def test_app_has_description(self):
        """Should have description"""
        assert hasattr(app, "description")
        assert len(app.description) > 0


class TestRouterInclusion:
    """Test that routers are included"""

    def test_system_routes_included(self):
        """System routes should be included"""
        client = TestClient(app)

        # Test that system routes exist
        response = client.get("/")
        assert response.status_code == 200

        response = client.get("/health")
        assert response.status_code == 200

    def test_routes_are_registered(self):
        """Routes should be registered in app"""
        # Get all routes
        routes = [route.path for route in app.routes]

        # Check system routes exist
        assert "/" in routes
        assert "/health" in routes
        assert "/api/init" in routes


class TestCORS:
    """Test CORS middleware"""

    def test_cors_allows_all_origins(self):
        """CORS should allow all origins (development)"""
        client = TestClient(app)

        # Make request with custom origin
        response = client.get(
            "/",
            headers={"Origin": "http://localhost:3000"}
        )

        # Check CORS headers are present
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_credentials(self):
        """CORS should allow credentials"""
        client = TestClient(app)

        # OPTIONS request
        response = client.options(
            "/",
            headers={"Origin": "http://localhost:3000"}
        )

        # Should have allow-credentials header
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "access-control-allow-credentials" in headers_lower


class TestExceptionHandling:
    """Test global exception handling"""

    def test_404_returns_json(self):
        """404 errors should return JSON"""
        client = TestClient(app)

        response = client.get("/nonexistent")

        # Should be JSON
        assert response.headers["content-type"] == "application/json"
        assert response.status_code == 404

    def test_404_has_detail(self):
        """404 should have detail message"""
        client = TestClient(app)

        response = client.get("/nonexistent")
        data = response.json()

        # FastAPI default 404 has 'detail'
        assert "detail" in data


class TestDocumentation:
    """Test API documentation endpoints"""

    def test_docs_endpoint_exists(self):
        """Should have /docs endpoint"""
        client = TestClient(app)

        response = client.get("/docs")

        # Should return HTML (Swagger UI)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint_exists(self):
        """Should have /redoc endpoint"""
        client = TestClient(app)

        response = client.get("/redoc")

        # Should return HTML (ReDoc)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json_exists(self):
        """Should have /openapi.json endpoint"""
        client = TestClient(app)

        response = client.get("/openapi.json")

        # Should return JSON schema
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_openapi_has_info(self):
        """OpenAPI schema should have info"""
        client = TestClient(app)

        response = client.get("/openapi.json")
        data = response.json()

        # Should have OpenAPI structure
        assert "info" in data
        assert "title" in data["info"]
        assert "version" in data["info"]


class TestApplicationLifecycle:
    """Test lifespan management"""

    def test_app_has_lifespan_context(self):
        """App should have lifespan context manager configured"""
        # FastAPI with lifespan has router.lifespan_context set
        assert hasattr(app.router, 'lifespan_context')
        assert app.router.lifespan_context is not None

    def test_lifespan_triggers_on_startup(self):
        """Lifespan context should trigger startup logic"""
        # Use context manager to trigger lifespan
        with TestClient(app) as client:
            # If lifespan works, app should be accessible
            response = client.get("/health")
            assert response.status_code == 200


class TestIntegration:
    """Integration tests for complete app"""

    def test_app_starts_successfully(self):
        """App should start without errors"""
        client = TestClient(app)

        # Should be able to make request
        response = client.get("/health")
        assert response.status_code == 200

    def test_multiple_requests_work(self):
        """Should handle multiple requests"""
        client = TestClient(app)

        # Make multiple requests
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200

    def test_different_methods_work(self):
        """Should handle different HTTP methods"""
        client = TestClient(app)

        # GET
        response = client.get("/health")
        assert response.status_code == 200

        # POST
        response = client.post("/api/init")
        assert response.status_code == 200
