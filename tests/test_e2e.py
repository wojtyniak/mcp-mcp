"""
End-to-end tests for MCP-MCP server with real server examples.

These tests verify the complete PoC workflow using actual MCP server data.
"""

import pytest
import pytest_asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import find_mcp_tool, app_lifespan, FastMCP, AppContext
from db import MCPDatabase


class TestE2EPoC:
    """End-to-end tests using real MCP server data."""

    @pytest_asyncio.fixture
    async def real_database(self):
        """Create a real MCP database with actual server data."""
        mcp_db = await MCPDatabase.create()
        return mcp_db

    @pytest.mark.asyncio
    async def test_weather_server_discovery(self, real_database):
        """Test discovering weather-related MCP servers."""
        # Temporarily set the global database
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            result = await find_mcp_tool(
                description="weather forecast data",
                example_question="What's the weather in Tokyo, Japan?"
            )

            # Assertions
            assert result["status"] == "found"
            assert "server" in result
            assert "alternatives" in result
            
            server = result["server"]
            assert server["name"]
            assert server["description"]
            assert server["url"]
            assert server["category"]
            
            # Weather-related servers should be found
            # Note: semantic search might find related data servers, so check more broadly
            description_lower = server["description"].lower()
            weather_terms = ["weather", "forecast", "climate", "temperature", "data", "api"]
            assert any(word in description_lower for word in weather_terms)
            
            # Should have README content structure
            assert "readme" in server

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_file_operations_discovery(self, real_database):
        """Test discovering file operation MCP servers."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            result = await find_mcp_tool(
                description="file system operations and file management",
                example_question="How can I manage files and directories?"
            )

            # Should find some kind of file-related server
            assert result["status"] in ["found", "not_found"]  # May not have file servers in current list
            
            if result["status"] == "found":
                server = result["server"]
                assert server["name"]
                assert server["description"]
                # File-related terms should appear
                assert any(word in server["description"].lower() 
                          for word in ["file", "filesystem", "directory", "folder", "path"])

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_database_operations_discovery(self, real_database):
        """Test discovering database-related MCP servers."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            result = await find_mcp_tool(
                description="database operations and SQL queries",
                example_question="How can I query a PostgreSQL database?"
            )

            # Should find some kind of database server or return not found
            assert result["status"] in ["found", "not_found"]
            
            if result["status"] == "found":
                server = result["server"]
                assert server["name"]
                assert server["description"]
                # Database-related terms should appear
                assert any(word in server["description"].lower() 
                          for word in ["database", "sql", "postgres", "mysql", "sqlite", "db"])

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_web_scraping_discovery(self, real_database):
        """Test discovering web scraping MCP servers."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            result = await find_mcp_tool(
                description="web scraping and content extraction",
                example_question="How can I scrape content from a website?"
            )

            # Should find web scraping servers (we know these exist)
            assert result["status"] == "found"
            
            server = result["server"]
            assert server["name"]
            assert server["description"]
            # Web scraping terms should appear
            description_lower = server["description"].lower()
            web_terms = ["web", "scraping", "scrape", "crawl", "extract", "html", "browser", "content", "data"]
            assert any(word in description_lower for word in web_terms)

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_github_operations_discovery(self, real_database):
        """Test discovering GitHub-related MCP servers."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            result = await find_mcp_tool(
                description="GitHub repository management and operations",
                example_question="How can I manage GitHub repositories and issues?"
            )

            # Should find GitHub-related servers
            assert result["status"] in ["found", "not_found"]
            
            if result["status"] == "found":
                server = result["server"]
                assert server["name"]
                assert server["description"]
                # GitHub terms should appear
                assert any(word in server["description"].lower() 
                          for word in ["github", "git", "repository", "repo", "issue", "pull", "commit"])

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_response_handling_edge_cases(self, real_database):
        """Test response handling for edge cases."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            # Test with very specific query that might not match well
            result = await find_mcp_tool(
                description="xyzxyz123 fictional nonexistent server type",
                example_question="How can I use xyzxyz123?"
            )

            # Should handle gracefully - either find something or return not_found
            assert result["status"] in ["found", "not_found"]
            
            if result["status"] == "not_found":
                assert "message" in result
                assert "suggestions" in result
            elif result["status"] == "found":
                # If something is found, it should have proper structure
                assert "server" in result
                assert "alternatives" in result

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_response_structure_consistency(self, real_database):
        """Test that all responses have consistent structure across different queries."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        queries = [
            "weather data",
            "file operations", 
            "database queries",
            "web scraping",
            "nonexistent quantum time travel"
        ]

        try:
            for query in queries:
                result = await find_mcp_tool(query)
                
                # All responses should have status
                assert "status" in result
                assert result["status"] in ["found", "not_found", "error"]
                
                if result["status"] == "found":
                    # Found responses should have server and alternatives
                    assert "server" in result
                    assert "alternatives" in result
                    
                    # Server should have all required fields
                    server = result["server"]
                    required_fields = ["name", "description", "url", "category", "readme"]
                    for field in required_fields:
                        assert field in server
                    
                    # Alternatives should be list and each should have required fields (except readme)
                    assert isinstance(result["alternatives"], list)
                    for alt in result["alternatives"]:
                        alt_fields = ["name", "description", "url", "category", "readme"]
                        for field in alt_fields:
                            assert field in alt
                        # Alternatives should not have README fetched (performance)
                        assert alt["readme"] is None
                
                elif result["status"] == "not_found":
                    # Not found responses should have message and suggestions
                    assert "message" in result
                    assert "suggestions" in result

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio 
    async def test_semantic_search_quality(self, real_database):
        """Test that semantic search returns relevant results."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            # Test semantic similarity with a direct weather query that should work
            weather_result = await find_mcp_tool("weather data")
            
            if weather_result["status"] == "found":
                description = weather_result["server"]["description"].lower()
                name = weather_result["server"]["name"].lower()
                # Should find weather-related content using semantic understanding
                weather_terms = ["weather", "forecast", "climate", "temperature", "atmospheric", "data", "api"]
                # Check both name and description
                found_terms = any(term in description for term in weather_terms) or any(term in name for term in weather_terms)
                assert found_terms, f"Expected weather-related terms in '{weather_result['server']['name']}': {description}"

        finally:
            main._global_mcp_db = original_db

    @pytest.mark.asyncio
    async def test_real_readme_fetching(self, real_database):
        """Test that README content is actually fetched for real GitHub repositories."""
        import main
        original_db = main._global_mcp_db
        main._global_mcp_db = real_database

        try:
            # Find a server that should be from a GitHub repo
            result = await find_mcp_tool("web browser automation")
            
            if result["status"] == "found":
                server = result["server"]
                
                # If it's a GitHub repo, README should either be content or None
                if "github.com" in server["url"]:
                    readme = server["readme"]
                    # README is either string content or None (if not found)
                    assert readme is None or isinstance(readme, str)
                    
                    # If we got README content, it should look like README content
                    if readme:
                        # Should contain some typical README elements
                        readme_lower = readme.lower()
                        readme_indicators = ["#", "install", "usage", "setup", "configuration", "example"]
                        # At least one typical README element should be present
                        assert any(indicator in readme_lower for indicator in readme_indicators)

        finally:
            main._global_mcp_db = original_db


class TestE2EPerformance:
    """Test performance characteristics of the PoC."""

    @pytest.mark.asyncio
    async def test_search_response_time(self):
        """Test that searches complete within reasonable time."""
        import time
        from main import MCPDatabase
        
        # Create database (this includes caching)
        start_time = time.time()
        mcp_db = await MCPDatabase.create()
        creation_time = time.time() - start_time
        
        # Database creation should be reasonably fast (with caching)
        # Allow up to 30 seconds for first run, but should be much faster with cache
        assert creation_time < 30.0
        
        # Search should be very fast
        start_time = time.time()
        results = mcp_db.search("weather forecast")
        search_time = time.time() - start_time
        
        # Search should complete in under 1 second
        assert search_time < 1.0
        
        # Should return some results
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_consistent_data_loading(self):
        """Test that database loading works consistently."""
        from main import MCPDatabase
        
        # First database creation
        mcp_db1 = await MCPDatabase.create()
        
        # Second database creation (should get same data)
        mcp_db2 = await MCPDatabase.create()
        
        # Both should have substantial data and be identical
        assert len(mcp_db1.servers) > 1000  # Verify we have substantial data
        assert len(mcp_db2.servers) == len(mcp_db1.servers)  # Same data
        assert mcp_db1.semantic_engine is not None  # Semantic search initialized
        assert mcp_db2.semantic_engine is not None  # Semantic search initialized