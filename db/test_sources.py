"""
Test suite for multi-source MCP server discovery.

Tests the new ServerSource implementations and deduplication logic.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from .sources import OfficialMCPSource, PunkpeyeAwesomeSource, AppcypherAwesomeSource, get_all_sources
from .database import MCPServerEntry, deduplicate_servers


class TestOfficialMCPSource:
    """Test the OfficialMCPSource implementation."""
    
    @pytest.mark.asyncio
    async def test_official_source_basic(self):
        """Test basic functionality of OfficialMCPSource."""
        source = OfficialMCPSource()
        assert source.name == "Official MCP Servers"
        assert "modelcontextprotocol/servers" in source.url
    
    def test_official_parse_sample_content(self):
        """Test parsing of official MCP server format."""
        sample_content = """
# MCP Servers

## 🌟 Reference Servers

- **[Weather](src/weather)** - Fetches weather data from the AccuWeather API
- **[Filesystem](src/filesystem)** - Provides file operations

### 🎖️ Official Integrations

- **[GitHub](src/github)** - GitHub API integration
        """
        
        source = OfficialMCPSource()
        servers = source.parse(sample_content)
        
        assert len(servers) == 3
        
        # Check first server
        weather = servers[0]
        assert weather.name == "Weather"
        assert "AccuWeather" in weather.description
        assert weather.category == "reference"
        assert weather.source == "official"
        assert "github.com/modelcontextprotocol/servers" in weather.url
        
        # Check official integration
        github = servers[2]
        assert github.name == "GitHub"
        assert github.category == "official"


class TestPunkpeyeAwesomeSource:
    """Test the PunkpeyeAwesomeSource implementation."""
    
    @pytest.mark.asyncio
    async def test_punkpeye_source_basic(self):
        """Test basic functionality of PunkpeyeAwesomeSource."""
        source = PunkpeyeAwesomeSource()
        assert source.name == "Punkpeye Awesome MCP Servers"
        assert "punkpeye/awesome-mcp-servers" in source.url
    
    def test_punkpeye_parse_sample_content(self):
        """Test parsing of punkpeye awesome servers format."""
        sample_content = """
# Awesome MCP Servers

## 🔗 Databases

- 🗄️ [mcp-database](https://github.com/example/mcp-database) - Database operations
- 📊 [mcp-sql](https://github.com/example/mcp-sql) 🐍 ☁️ - SQL query execution

## 🎨 Art & Culture

- 🖼️ [mcp-gallery](https://github.com/example/mcp-gallery) - Art gallery management
        """
        
        source = PunkpeyeAwesomeSource()
        servers = source.parse(sample_content)
        
        assert len(servers) == 3
        
        # Check database server
        db_server = servers[0]
        assert db_server.name == "mcp-database"
        assert "Database operations" in db_server.description
        assert db_server.category == "databases"
        assert db_server.source == "punkpeye-awesome"
        
        # Check SQL server with icons
        sql_server = servers[1]
        assert sql_server.name == "mcp-sql"
        assert "SQL query execution" in sql_server.description


class TestAppcypherAwesomeSource:
    """Test the AppcypherAwesomeSource implementation."""
    
    @pytest.mark.asyncio
    async def test_appcypher_source_basic(self):
        """Test basic functionality of AppcypherAwesomeSource."""
        source = AppcypherAwesomeSource()
        assert source.name == "Appcypher Awesome MCP Servers"
        assert "appcypher/awesome-mcp-servers" in source.url
    
    def test_appcypher_parse_sample_content(self):
        """Test parsing of appcypher awesome servers format."""
        sample_content = """
# Awesome MCP Servers

## File Systems

- <img src="icon.png" width="16"> [mcp-filesystem](https://github.com/example/mcp-filesystem) - File operations
- [mcp-storage](https://github.com/example/mcp-storage) - Cloud storage

## Communication

- [mcp-slack](https://github.com/example/mcp-slack) - Slack integration
        """
        
        source = AppcypherAwesomeSource()
        servers = source.parse(sample_content)
        
        assert len(servers) == 3
        
        # Check filesystem server (with img tag)
        fs_server = servers[0]
        assert fs_server.name == "mcp-filesystem"
        assert "File operations" in fs_server.description
        assert fs_server.category == "file-systems"
        assert fs_server.source == "appcypher-awesome"
        
        # Check slack server
        slack_server = servers[2]
        assert slack_server.name == "mcp-slack"
        assert slack_server.category == "communication"


class TestDeduplication:
    """Test server deduplication logic."""
    
    def test_deduplicate_no_duplicates(self):
        """Test deduplication when there are no duplicates."""
        servers = [
            MCPServerEntry("Server1", "Description1", "https://github.com/example/server1", "cat1", "source1"),
            MCPServerEntry("Server2", "Description2", "https://github.com/example/server2", "cat2", "source2"),
        ]
        
        result = deduplicate_servers(servers)
        assert len(result) == 2
        assert result == servers
    
    def test_deduplicate_with_duplicates(self):
        """Test deduplication when there are actual duplicates."""
        servers = [
            MCPServerEntry("Weather Server", "Basic weather data", "https://github.com/example/weather", "reference", "official"),
            MCPServerEntry("Weather Server", "Advanced weather forecasting with AccuWeather API", "https://github.com/example/weather", "tools", "punkpeye-awesome"),
            MCPServerEntry("Other Server", "Different server", "https://github.com/example/other", "tools", "official"),
        ]
        
        result = deduplicate_servers(servers)
        assert len(result) == 2
        
        # Find the deduplicated weather server
        weather_server = next(s for s in result if "weather" in s.url)
        assert weather_server.name == "Weather Server"
        # Should use the longer, more descriptive description
        assert "AccuWeather API" in weather_server.description
        # Should combine source information
        assert "punkpeye-awesome" in weather_server.source
        assert "official" in weather_server.source
    
    def test_deduplicate_merges_all_descriptions(self):
        """Test that deduplication merges all unique descriptions."""
        servers = [
            MCPServerEntry("Test Server", "MCP server for testing", "https://github.com/example/test", "tools", "source1"),
            MCPServerEntry("Test Server", "Comprehensive testing framework for MCP", "https://github.com/example/test", "tools", "source2"),
        ]
        
        result = deduplicate_servers(servers)
        assert len(result) == 1
        
        # Should merge both descriptions
        assert "MCP server for testing" in result[0].description
        assert "Comprehensive testing framework for MCP" in result[0].description
        assert ";" in result[0].description  # Separator
        assert result[0].source == "source1+source2"


class TestGetAllSources:
    """Test the get_all_sources function."""
    
    def test_get_all_sources_returns_expected_sources(self):
        """Test that get_all_sources returns all expected source types."""
        sources = get_all_sources()
        
        assert len(sources) == 3
        
        source_types = [type(source).__name__ for source in sources]
        assert "OfficialMCPSource" in source_types
        assert "PunkpeyeAwesomeSource" in source_types
        assert "AppcypherAwesomeSource" in source_types
    
    def test_all_sources_have_required_methods(self):
        """Test that all sources implement required methods."""
        sources = get_all_sources()
        
        for source in sources:
            assert hasattr(source, 'fetch')
            assert hasattr(source, 'parse')
            assert hasattr(source, 'get_servers')
            assert hasattr(source, 'name')
            assert hasattr(source, 'url')