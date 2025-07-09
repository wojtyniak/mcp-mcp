"""
Test Origin validation middleware for security.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from starlette.responses import Response
from main import OriginValidationMiddleware


class TestOriginValidation:
    """Test the Origin validation middleware."""

    @pytest.mark.asyncio
    async def test_origin_middleware_allows_valid_origins(self):
        """Test that valid origins are allowed."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        
        # Mock next handler
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # Test valid origins
        valid_origins = [
            "http://localhost",
            "https://localhost", 
            "http://localhost:8000",
            "http://127.0.0.1",
            "https://127.0.0.1:8000",
        ]
        
        for origin in valid_origins:
            # Create mock request with valid origin and host
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"origin": origin, "host": "localhost:8000"}
            
            response = await middleware.dispatch(mock_request, mock_next)
            
            # Should call next handler (not blocked)
            assert response.status_code == 200, f"Origin {origin} should be allowed"
            mock_next.assert_called_with(mock_request)

    @pytest.mark.asyncio
    async def test_origin_middleware_blocks_invalid_origins(self):
        """Test that invalid origins are blocked."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # Invalid origins should be blocked
        invalid_origins = [
            "http://evil.com",
            "https://attacker.net",
            "http://malicious.example.com",
            "https://phishing.site",
        ]
        
        for origin in invalid_origins:
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"origin": origin, "host": "localhost:8000"}
            
            response = await middleware.dispatch(mock_request, mock_next)
            
            assert response.status_code == 403, f"Origin {origin} should be blocked"
            assert "Invalid origin header" in response.body.decode()

    @pytest.mark.asyncio
    async def test_origin_middleware_allows_no_origin(self):
        """Test that requests without Origin header are allowed."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # No origin header should be allowed (many legitimate requests don't have it)
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"host": "localhost:8000"}  # No origin header
        
        response = await middleware.dispatch(mock_request, mock_next)
        
        assert response.status_code == 200  # Not 403
        mock_next.assert_called_with(mock_request)

    @pytest.mark.asyncio
    async def test_host_header_validation(self):
        """Test that invalid Host headers are blocked."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # Invalid host headers should be blocked
        invalid_hosts = [
            "evil.com",
            "attacker.net:8000",
            "malicious.example.com:443",
        ]
        
        for host in invalid_hosts:
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"host": host}  # No origin, just invalid host
            
            response = await middleware.dispatch(mock_request, mock_next)
            
            assert response.status_code == 403, f"Host {host} should be blocked"
            assert "Invalid host header" in response.body.decode()

    @pytest.mark.asyncio
    async def test_valid_host_headers(self):
        """Test that valid Host headers are allowed."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # Valid host headers should be allowed
        valid_hosts = [
            "localhost",
            "localhost:8000",
            "127.0.0.1",
            "127.0.0.1:8080",
        ]
        
        for host in valid_hosts:
            mock_request = MagicMock(spec=Request)
            mock_request.headers = {"host": host}
            
            response = await middleware.dispatch(mock_request, mock_next)
            
            assert response.status_code == 200, f"Host {host} should be allowed"  # Not 403
            mock_next.assert_called_with(mock_request)

    @pytest.mark.asyncio
    async def test_combined_origin_and_host_validation(self):
        """Test combined Origin and Host header validation."""
        middleware = OriginValidationMiddleware(None, ["localhost", "127.0.0.1"])
        mock_next = AsyncMock(return_value=Response("OK", 200))
        
        # Both valid should work
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"origin": "http://localhost:8000", "host": "localhost:8000"}
        
        response = await middleware.dispatch(mock_request, mock_next)
        assert response.status_code == 200  # Not 403
        mock_next.assert_called_with(mock_request)
        
        # Invalid origin should be blocked even with valid host
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"origin": "http://evil.com", "host": "localhost:8000"}
        
        response = await middleware.dispatch(mock_request, mock_next)
        assert response.status_code == 403
        assert "Invalid origin header" in response.body.decode()
        
        # Invalid host should be blocked even with valid origin
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"origin": "http://localhost:8000", "host": "evil.com"}
        
        response = await middleware.dispatch(mock_request, mock_next)
        assert response.status_code == 403
        assert "Invalid host header" in response.body.decode()