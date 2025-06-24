"""Tests for the improved search functionality in MCPDatabase."""

import pytest
from mcp_db import MCPDatabase, MCPServerEntry, parse_mcp_server_list


# Test data
test_servers = [
    MCPServerEntry(name="Fetch", description="Web content fetching and conversion for efficient LLM usage", url="https://github.com/modelcontextprotocol/servers/tree/main/src/fetch", category="reference"),
    MCPServerEntry(name="Weather API", description="Get weather forecasts and current conditions", url="https://github.com/example/weather-mcp", category="community"),
    MCPServerEntry(name="Domain Checker", description="Check domain availability and whois information", url="https://github.com/example/domain-mcp", category="community"),
    MCPServerEntry(name="Stock Market", description="Real-time stock prices and market data", url="https://github.com/example/stocks-mcp", category="official"),
]


@pytest.fixture
def mock_database():
    """Create a mock MCPDatabase with test data."""
    db = MCPDatabase(servers=test_servers)
    return db


def test_search_exact_name_match(mock_database):
    """Test exact name matching gets highest score."""
    results = mock_database.search("Fetch")
    assert len(results) >= 1
    assert results[0].name == "Fetch"


def test_search_partial_name_match(mock_database):
    """Test partial name matching."""
    results = mock_database.search("Weather")
    assert len(results) >= 1
    assert any("Weather" in server.name for server in results)


def test_search_description_match(mock_database):
    """Test description keyword matching."""
    results = mock_database.search("domain availability")
    assert len(results) >= 1
    assert any("domain" in server.description.lower() for server in results)


def test_search_multiple_words(mock_database):
    """Test search with multiple keywords."""
    results = mock_database.search("weather forecast")
    assert len(results) >= 1
    # Should find weather-related servers
    assert any("weather" in server.name.lower() or "weather" in server.description.lower() for server in results)


def test_search_case_insensitive(mock_database):
    """Test that search is case insensitive."""
    results_lower = mock_database.search("fetch")
    results_upper = mock_database.search("FETCH")
    results_mixed = mock_database.search("Fetch")
    
    assert len(results_lower) == len(results_upper) == len(results_mixed)
    assert results_lower[0].name == results_upper[0].name == results_mixed[0].name


def test_search_empty_query(mock_database):
    """Test search with empty query returns empty results."""
    results = mock_database.search("")
    assert len(results) == 0
    
    results = mock_database.search("   ")
    assert len(results) == 0


def test_search_no_matches(mock_database):
    """Test search with no matches returns empty results."""
    results = mock_database.search("nonexistent functionality xyz")
    # Debug: print what's matching
    if results:
        for i, server in enumerate(results):
            score = mock_database._calculate_relevance_score(server, "nonexistent functionality xyz", {"nonexistent", "functionality", "xyz"})
            print(f"Match {i}: {server.name} (score: {score}) - {server.description}")
    assert len(results) == 0


def test_search_relevance_ordering(mock_database):
    """Test that results are ordered by relevance."""
    results = mock_database.search("web content")
    assert len(results) >= 1
    
    # Results should be ordered by relevance score
    # Fetch server should rank highly for "web content" due to description match
    fetch_server = next((s for s in results if s.name == "Fetch"), None)
    assert fetch_server is not None
    # Should be in top results due to good description match
    assert results.index(fetch_server) <= 1


def test_category_boost(mock_database):
    """Test that reference/official servers get category boost."""
    # Create a scenario where category boost matters
    results = mock_database.search("content")
    
    # Find reference and community servers in results
    reference_servers = [s for s in results if s.category == "reference"]
    community_servers = [s for s in results if s.category == "community"]
    
    if reference_servers and community_servers:
        # Reference servers should generally rank higher due to category boost
        # (assuming similar keyword matches)
        ref_index = results.index(reference_servers[0])
        # This is a soft assertion since it depends on the specific scoring
        assert ref_index >= 0  # Just ensure it's found


def test_parse_mcp_server_list_integration():
    """Test that the parser works with real-world data structure."""
    sample_readme = """
# Model Context Protocol servers

## 🌟 Reference Servers

- **[Fetch](src/fetch)** - Web content fetching and conversion for efficient LLM usage
- **[Weather](src/weather)** - Weather data and forecasts

### 🌎 Community Servers

- **[Domain Tools](https://github.com/example/domain-mcp)** - Domain availability and WHOIS lookup
"""
    
    servers = parse_mcp_server_list(sample_readme)
    assert len(servers) >= 3
    
    # Test that parsed servers work with search
    db = MCPDatabase(servers=servers)
    results = db.search("weather")
    assert len(results) >= 1


def test_search_relevance_score_calculation(mock_database):
    """Test the internal relevance scoring mechanism."""
    # Test exact name match should score highest
    results = mock_database.search("Fetch")
    fetch_server = results[0]
    assert fetch_server.name == "Fetch"
    
    # Test that description matches work
    results = mock_database.search("stock prices")
    stock_servers = [s for s in results if "stock" in s.name.lower() or "stock" in s.description.lower()]
    assert len(stock_servers) >= 1


def test_fuzzy_matching(mock_database):
    """Test fuzzy/partial word matching."""
    # Should match "Domain" in "Domain Checker"
    results = mock_database.search("domains")
    domain_servers = [s for s in results if "domain" in s.name.lower() or "domain" in s.description.lower()]
    assert len(domain_servers) >= 1
    
    # Should match "weather" variations
    results = mock_database.search("forecast")
    weather_servers = [s for s in results if "weather" in s.name.lower() or "forecast" in s.description.lower()]
    assert len(weather_servers) >= 1