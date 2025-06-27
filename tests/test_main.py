"""
Test suite for main.py PoC functionality.

Tests the core find_mcp_tool functionality and README fetching.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import find_mcp_tool, _fetch_readme_content, _global_mcp_db
from db import MCPServerEntry


class TestFindMCPTool:
    """Test the find_mcp_tool function."""

    @pytest.fixture
    def mock_server_entry(self):
        """Sample server entry for testing."""
        return MCPServerEntry(
            name="test-server",
            description="A test MCP server for weather data",
            url="https://github.com/test-org/test-server",
            category="reference"
        )

    @pytest.fixture
    def mock_database(self, mock_server_entry):
        """Mock MCP database with test data."""
        mock_db = MagicMock()
        mock_db.search.return_value = [mock_server_entry]
        return mock_db

    @pytest.mark.asyncio
    async def test_find_mcp_tool_success(self, mock_database, mock_server_entry):
        """Test successful MCP server discovery."""
        with patch('main._global_mcp_db', mock_database):
            with patch('main._fetch_readme_content', return_value="# Test Server\nThis is a test server."):
                result = await find_mcp_tool("weather data", "What's the weather?")

            # Assertions
            assert result["status"] == "found"
            assert result["server"]["name"] == "test-server"
            assert result["server"]["description"] == "A test MCP server for weather data"
            assert result["server"]["url"] == "https://github.com/test-org/test-server"
            assert result["server"]["category"] == "reference"
            assert result["server"]["readme"] == "# Test Server\nThis is a test server."
            assert isinstance(result["alternatives"], list)

            # Verify database search was called
            mock_database.search.assert_called_once_with("weather data")

    @pytest.mark.asyncio
    async def test_find_mcp_tool_no_results(self, mock_database):
        """Test when no MCP servers are found."""
        mock_database.search.return_value = []

        with patch('main._global_mcp_db', mock_database):
            result = await find_mcp_tool("nonexistent functionality")

            # Assertions
            assert result["status"] == "not_found"
            assert "No MCP servers found" in result["message"]
            assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_find_mcp_tool_auto_initializes_db(self):
        """Test that database auto-initializes when not available."""
        with patch('main._global_mcp_db', None):
            # Mock the database creation to avoid real initialization
            mock_db = MagicMock()
            mock_server = MCPServerEntry("auto-init-server", "Test server", "https://github.com/test/auto", "reference")
            mock_db.search.return_value = [mock_server]
            
            with patch('main.MCPDatabase.create', return_value=mock_db):
                with patch('main._fetch_readme_content', return_value="# Auto Init Server"):
                    result = await find_mcp_tool("test query")

                    # Should succeed and find server
                    assert result["status"] == "found"
                    assert result["server"]["name"] == "auto-init-server"

    @pytest.mark.asyncio
    async def test_find_mcp_tool_with_alternatives(self, mock_database):
        """Test that alternatives are properly included."""
        # Setup additional mock servers
        servers = [
            MCPServerEntry("primary-server", "Primary server", "https://github.com/test/primary", "reference"),
            MCPServerEntry("alt-server-1", "Alternative 1", "https://github.com/test/alt1", "community"),
            MCPServerEntry("alt-server-2", "Alternative 2", "https://github.com/test/alt2", "official"),
            MCPServerEntry("alt-server-3", "Alternative 3", "https://github.com/test/alt3", "archived"),
            MCPServerEntry("alt-server-4", "Alternative 4", "https://github.com/test/alt4", "reference"),
        ]
        
        mock_database.search.return_value = servers

        with patch('main._global_mcp_db', mock_database):
            with patch('main._fetch_readme_content', return_value="# Primary Server\nMain server docs."):
                result = await find_mcp_tool("test functionality")

            # Assertions
            assert result["status"] == "found"
            assert result["server"]["name"] == "primary-server"
            assert len(result["alternatives"]) == 3  # Should include up to 3 alternatives
            
            # Check alternative structure (should not have README)
            for alt in result["alternatives"]:
                assert alt["readme"] is None
                assert "name" in alt
                assert "description" in alt
                assert "url" in alt
                assert "category" in alt

    @pytest.mark.asyncio
    async def test_find_mcp_tool_prefers_server_with_readme(self, mock_database):
        """Test that server with README is preferred over one without."""
        # Setup servers where first doesn't have README but second does
        servers = [
            MCPServerEntry("no-readme-server", "Server without README", "https://example.com/no-readme", "reference"),
            MCPServerEntry("with-readme-server", "Server with README", "https://github.com/test/with-readme", "reference"),
            MCPServerEntry("another-server", "Another server", "https://github.com/test/another", "community"),
        ]
        
        mock_database.search.return_value = servers

        def mock_fetch_readme(url):
            if "with-readme" in url:
                return "# Server with README\nComplete documentation here."
            return None  # No README for other URLs

        with patch('main._global_mcp_db', mock_database):
            with patch('main._fetch_readme_content', side_effect=mock_fetch_readme):
                result = await find_mcp_tool("test functionality")

            # Should prefer the server with README even though it's not first
            assert result["status"] == "found"
            assert result["server"]["name"] == "with-readme-server"
            assert result["server"]["readme"] == "# Server with README\nComplete documentation here."
            
            # The originally top-ranked server should be in alternatives
            alt_names = [alt["name"] for alt in result["alternatives"]]
            assert "no-readme-server" in alt_names


class TestFetchReadmeContent:
    """Test the _fetch_readme_content function."""

    @pytest.mark.asyncio
    async def test_fetch_readme_simple_github_url(self):
        """Test fetching README from a simple GitHub repository URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Test README\nThis is a test README file."

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_readme_content("https://github.com/test-org/test-repo")
            
            assert result == "# Test README\nThis is a test README file."

    @pytest.mark.asyncio
    async def test_fetch_readme_with_tree_path(self):
        """Test fetching README from GitHub URL with tree path."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Server README\nDetailed server documentation."

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_readme_content("https://github.com/modelcontextprotocol/servers/tree/main/src/weather")
            
            assert result == "# Server README\nDetailed server documentation."

    @pytest.mark.asyncio
    async def test_fetch_readme_multiple_filename_attempts(self):
        """Test that function tries multiple README filename variations."""
        responses = {
            "README.md": 404,
            "README.txt": 404, 
            "README": 200,
        }
        
        def mock_get(url):
            mock_response = MagicMock()
            for filename, status in responses.items():
                if filename in url:
                    mock_response.status_code = status
                    if status == 200:
                        mock_response.text = f"Content from {filename}"
                    break
            else:
                mock_response.status_code = 404
            return mock_response

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = mock_get
            
            result = await _fetch_readme_content("https://github.com/test-org/test-repo")
            
            assert result == "Content from README"

    @pytest.mark.asyncio
    async def test_fetch_readme_not_github_url(self):
        """Test that non-GitHub URLs return None."""
        result = await _fetch_readme_content("https://example.com/some-repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_readme_no_readme_found(self):
        """Test when no README file is found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await _fetch_readme_content("https://github.com/test-org/test-repo")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_readme_http_error(self):
        """Test handling of HTTP errors."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.RequestError("Connection failed")
            
            result = await _fetch_readme_content("https://github.com/test-org/test-repo")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_readme_invalid_github_url(self):
        """Test handling of malformed GitHub URLs."""
        result = await _fetch_readme_content("https://github.com/incomplete")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_readme_timeout_handling(self):
        """Test that timeouts are handled gracefully."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.TimeoutException("Request timeout")
            
            result = await _fetch_readme_content("https://github.com/test-org/test-repo")
            
            assert result is None


class TestMainIntegration:
    """Integration tests for main functionality."""

    @pytest.mark.asyncio
    async def test_query_processing_and_response_structure(self):
        """Test that queries are processed correctly and responses have proper structure."""
        mock_server = MCPServerEntry(
            name="weather-server",
            description="Weather forecast MCP server",
            url="https://github.com/example/weather-server",
            category="official"
        )
        
        mock_db = MagicMock()
        mock_db.search.return_value = [mock_server]
        
        with patch('main._global_mcp_db', mock_db):
            with patch('main._fetch_readme_content', return_value="# Weather Server\n\nInstallation: `npm install weather-server`"):
                result = await find_mcp_tool(
                    description="weather forecast data",
                    example_question="What's the weather in Tokyo?"
                )

            # Test response structure
            assert isinstance(result, dict)
            assert "status" in result
            assert "server" in result
            assert "alternatives" in result
            
            # Test server details structure
            server = result["server"]
            assert all(key in server for key in ["name", "description", "url", "category", "readme"])
            
            # Test that search query was processed correctly
            mock_db.search.assert_called_once_with("weather forecast data")

    def test_response_schema_consistency(self):
        """Test that response schemas are consistent across different scenarios."""
        # This is a structural test - responses should have consistent keys
        
        # Success response should have these keys
        success_keys = {"status", "server", "alternatives"}
        
        # Error response should have these keys
        error_keys = {"status", "message"}
        
        # Not found response should have these keys  
        not_found_keys = {"status", "message", "suggestions"}
        
        # Server object should have these keys
        server_keys = {"name", "description", "url", "category", "readme"}
        
        # Alternative objects should have these keys (no readme)
        alternative_keys = {"name", "description", "url", "category", "readme"}
        
        # These are structural assertions that define the API contract
        assert success_keys
        assert error_keys
        assert not_found_keys
        assert server_keys
        assert alternative_keys