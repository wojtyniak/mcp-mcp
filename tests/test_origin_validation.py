"""
Test Origin validation middleware for security.
"""

import pytest
from starlette.testclient import TestClient
from main import mcp, OriginValidationMiddleware


class TestOriginValidation:
    """Test the Origin validation middleware."""

    def test_origin_middleware_allows_valid_origins(self):
        """Test that valid origins are allowed."""
        # Create a test app with middleware - testserver needs to be allowed in production code for tests
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
        
        client = TestClient(app)
        
        # Valid origins should be allowed
        valid_origins = [
            "http://localhost",
            "https://localhost", 
            "http://localhost:8000",
            "http://127.0.0.1",
            "https://127.0.0.1:8000",
        ]
        
        for origin in valid_origins:
            response = client.get("/", headers={"Origin": origin})
            # Should get 404 (endpoint doesn't exist) not 403 (forbidden)
            assert response.status_code == 404, f"Origin {origin} should be allowed"

    def test_origin_middleware_blocks_invalid_origins(self):
        """Test that invalid origins are blocked."""
        # Create a test app with middleware - include all local hosts for TestClient compatibility
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
        
        client = TestClient(app)
        
        # Invalid origins should be blocked
        invalid_origins = [
            "http://evil.com",
            "https://attacker.net",
            "http://malicious.example.com",
            "https://phishing.site",
        ]
        
        for origin in invalid_origins:
            response = client.get("/", headers={"Origin": origin})
            assert response.status_code == 403, f"Origin {origin} should be blocked"
            assert "Invalid origin header" in response.text

    def test_origin_middleware_allows_no_origin(self):
        """Test that requests without Origin header are allowed."""
        # Create a test app with middleware - include "testserver" for TestClient compatibility  
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "testserver"])
        
        client = TestClient(app)
        
        # No origin header should be allowed (many legitimate requests don't have it)
        response = client.get("/")
        assert response.status_code == 404  # Not 403

    def test_host_header_validation(self):
        """Test that invalid Host headers are blocked."""
        # Create a test app with middleware - include all local hosts for TestClient compatibility
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
        
        client = TestClient(app)
        
        # Invalid host headers should be blocked
        invalid_hosts = [
            "evil.com",
            "attacker.net:8000",
            "malicious.example.com:443",
        ]
        
        for host in invalid_hosts:
            response = client.get("/", headers={"Host": host})
            assert response.status_code == 403, f"Host {host} should be blocked"
            assert "Invalid host header" in response.text

    def test_valid_host_headers(self):
        """Test that valid Host headers are allowed."""
        # Create a test app with middleware  
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost"])
        
        client = TestClient(app)
        
        # Valid host headers should be allowed
        valid_hosts = [
            "localhost",
            "localhost:8000",
            "127.0.0.1",
            "127.0.0.1:8080",
        ]
        
        for host in valid_hosts:
            response = client.get("/", headers={"Host": host})
            assert response.status_code == 404, f"Host {host} should be allowed"  # Not 403

    def test_combined_origin_and_host_validation(self):
        """Test combined Origin and Host header validation."""
        # Create a test app with middleware - include all local hosts for TestClient compatibility
        app = mcp.streamable_http_app()
        app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
        
        client = TestClient(app)
        
        # Both valid should work
        response = client.get("/", headers={
            "Origin": "http://localhost:8000",
            "Host": "localhost:8000"
        })
        assert response.status_code == 404  # Not 403
        
        # Invalid origin should be blocked even with valid host
        response = client.get("/", headers={
            "Origin": "http://evil.com",
            "Host": "localhost:8000"
        })
        assert response.status_code == 403
        assert "Invalid origin header" in response.text
        
        # Invalid host should be blocked even with valid origin
        response = client.get("/", headers={
            "Origin": "http://localhost:8000", 
            "Host": "evil.com"
        })
        assert response.status_code == 403
        assert "Invalid host header" in response.text