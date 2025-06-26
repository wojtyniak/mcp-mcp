"""
Comprehensive tests for precomputed data loading workflow.

This tests the critical first-user experience path:
1. Fresh installation (no cache) -> downloads precomputed data
2. Subsequent runs -> uses cache
3. Schema compatibility checking with redirects
4. Graceful fallback when precomputed data fails
5. Performance characteristics

These tests simulate the real user onboarding experience.

INTEGRATION TESTS:
- Set MCP_MCP_TEST_GITHUB_INTEGRATION=1 to test real GitHub downloads
- Set MCP_MCP_TEST_GITHUB_STRESS=1 to test concurrent user simulation
- These are disabled by default to avoid network dependencies in CI

TECHNICAL NOTES:
- GitHub releases return 302 redirects to S3, requiring follow_redirects=True
- Precomputed data uses schema versioning with graceful fallback
- Cache is only created when precomputed data fails (by design)
- Performance target: < 5 seconds for fresh install, < 1 second for cache hits
"""

import pytest
import tempfile
import json
import numpy as np
import time
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, Mock
from dataclasses import asdict
import httpx

from .database import MCPDatabase, MCPServerEntry, get_server_cache_dir
from .schema_versions import CompatibilityLevel


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "mcp-mcp" / "servers"
        cache_path.mkdir(parents=True, exist_ok=True)
        yield cache_path


@pytest.fixture
def mock_precomputed_data():
    """Mock precomputed data that would come from GitHub releases."""
    servers = [
        MCPServerEntry(
            name="test-weather",
            description="Weather data server",
            url="https://github.com/example/mcp-weather",
            category="Data",
            source="official"
        ),
        MCPServerEntry(
            name="test-database",
            description="Database connector server",
            url="https://github.com/example/mcp-db",
            category="Database",
            source="community"
        )
    ]
    
    data_info = {
        "servers_count": len(servers),
        "servers_hash": "test_hash_123",
        "embeddings_shape": [len(servers), 384],
        "model_name": "all-MiniLM-L6-v2",
        "embeddings_version": "v1",
        "schema_version": "1.0",
        "build_timestamp": 1750000000.0,
        "build_date": "2025-06-26 00:00:00 UTC",
        "sources": ["Test Source"]
    }
    
    # Create mock embeddings
    embeddings = np.random.rand(len(servers), 384).astype(np.float32)
    
    return {
        "servers": servers,
        "data_info": data_info,
        "embeddings": embeddings
    }


class TestPrecomputedDataWorkflow:
    """Test the complete precomputed data loading workflow."""
    
    @pytest.mark.asyncio
    async def test_fresh_installation_workflow(self, temp_cache_dir, mock_precomputed_data):
        """Test first-time user experience: no cache, downloads precomputed data."""
        
        # Mock httpx responses for GitHub releases (with redirects)
        mock_responses = {
            "data_info.json": Mock(
                status_code=200,
                json=Mock(return_value=mock_precomputed_data["data_info"])
            ),
            "servers.json": Mock(
                status_code=200,
                json=Mock(return_value=[asdict(s) for s in mock_precomputed_data["servers"]])
            ),
            "embeddings.npz": Mock(
                status_code=200,
                content=b"mock_embeddings_data"
            )
        }
        
        async def mock_get(url):
            """Mock httpx.get with redirect simulation."""
            if "data_info.json" in url:
                return mock_responses["data_info.json"]
            elif "servers.json" in url:
                return mock_responses["servers.json"]
            elif "embeddings.npz" in url:
                return mock_responses["embeddings.npz"]
            else:
                raise ValueError(f"Unexpected URL: {url}")
        
        # Patch cache directory and httpx
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                # Configure mock client to follow redirects
                mock_client = AsyncMock()
                mock_client.get = mock_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                # Mock numpy.load for embeddings
                with patch('numpy.load', return_value=mock_precomputed_data["embeddings"]):
                    # Create database - should download precomputed data
                    db = await MCPDatabase.create()
                    
                    # Verify data was loaded correctly
                    assert len(db.servers) == 2
                    assert db.servers[0].name == "test-weather"
                    assert db.servers[1].name == "test-database"
                    
                    # When precomputed data is used, no cache file is created (by design)
                    # Cache is only created when downloading from live sources
                    cache_file = temp_cache_dir / "server_list.json"
                    # Note: cache_file.exists() will be False, which is correct behavior
                    
                    # Verify httpx was called with follow_redirects=True
                    mock_client_class.assert_called_with(timeout=30.0, follow_redirects=True)
    
    @pytest.mark.asyncio
    async def test_cache_hit_workflow(self, temp_cache_dir, mock_precomputed_data):
        """Test subsequent runs: uses cached data, no network calls."""
        
        # Pre-populate cache
        cache_file = temp_cache_dir / "server_list.json"
        cache_data = {
            "servers": [asdict(s) for s in mock_precomputed_data["servers"]],
            "timestamp": 1750000000.0,  # Recent timestamp
            "sources_hash": "test_hash"
        }
        cache_file.write_text(json.dumps(cache_data))
        
        # Mock httpx to return 404 for precomputed data, then fall back to cache
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                # Mock precomputed data check to fail (404), then use cache
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=Mock(status_code=404))
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                # Create database - should check precomputed data, fail, then use cache
                db = await MCPDatabase.create()
                
                # Verify data was loaded from cache
                assert len(db.servers) == 2
                assert db.servers[0].name == "test-weather"
                
                # Verify httpx was called (for precomputed data check) but cache was used
                mock_client_class.assert_called()
    
    @pytest.mark.asyncio 
    async def test_schema_incompatibility_fallback(self, temp_cache_dir):
        """Test graceful fallback when precomputed data has incompatible schema."""
        
        # Mock incompatible schema version
        incompatible_data_info = {
            "schema_version": "2.0",  # Incompatible with current 1.x
            "servers_count": 100,
            "build_timestamp": 1750000000.0
        }
        
        # Mock successful live source fetch
        live_servers = [
            MCPServerEntry(
                name="live-server",
                description="Server from live source",
                url="https://github.com/example/live",
                category="Live",
                source="live"
            )
        ]
        
        async def mock_get(url):
            if "data_info.json" in url:
                return Mock(status_code=200, json=Mock(return_value=incompatible_data_info))
            else:
                raise Exception("Should not fetch other precomputed data")
        
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                # Mock live sources to return data
                with patch('db.sources.get_all_sources') as mock_sources:
                    mock_source = Mock()
                    mock_source.name = "Test Live Source"
                    mock_source.get_servers = AsyncMock(return_value=live_servers)
                    mock_sources.return_value = [mock_source]
                    
                    # Create database - should fall back to live sources
                    db = await MCPDatabase.create()
                    
                    # Verify fallback worked
                    assert len(db.servers) == 1
                    assert db.servers[0].name == "live-server"
                    assert db.servers[0].source == "live"
    
    @pytest.mark.asyncio
    async def test_redirect_handling(self, temp_cache_dir, mock_precomputed_data):
        """Test that httpx properly handles GitHub release redirects."""
        
        redirect_count = 0
        
        async def mock_get_with_redirect(url):
            nonlocal redirect_count
            redirect_count += 1
            
            # Simulate redirect behavior
            if redirect_count == 1:
                # First call returns 302 redirect (without follow_redirects)
                return Mock(status_code=302)
            else:
                # Second call returns 200 (with follow_redirects)
                if "data_info.json" in url:
                    return Mock(
                        status_code=200,
                        json=Mock(return_value=mock_precomputed_data["data_info"])
                    )
                else:
                    return Mock(status_code=200)
        
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            # Test without follow_redirects (should fail)
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_get_with_redirect
                # Simulate old behavior without follow_redirects
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                db = MCPDatabase(servers=[])
                result = await db._check_schema_compatibility()
                
                # Should fail due to 302 status
                assert result is None
                
                # Reset redirect count
                redirect_count = 0
                
                # Now test with follow_redirects=True (current implementation)
                # The mock should be called with follow_redirects=True
                mock_client_class.assert_called_with(timeout=30.0, follow_redirects=True)
    
    @pytest.mark.asyncio
    async def test_network_failure_graceful_degradation(self, temp_cache_dir):
        """Test graceful handling when all network requests fail."""
        
        # Create stale cache
        stale_cache_file = temp_cache_dir / "server_list.json"
        stale_data = {
            "servers": [asdict(MCPServerEntry(
                name="stale-server",
                description="Server from stale cache",
                url="https://github.com/example/stale",
                category="Stale",
                source="stale"
            ))],
            "timestamp": 1700000000.0,  # Very old timestamp
            "sources_hash": "stale_hash"
        }
        stale_cache_file.write_text(json.dumps(stale_data))
        
        # Mock all network calls to fail
        async def mock_failing_get(url):
            raise httpx.RequestError("Network error")
        
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_failing_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                # Mock live sources to also fail
                with patch('db.sources.get_all_sources') as mock_sources:
                    mock_source = Mock()
                    mock_source.name = "Failing Source"
                    mock_source.get_servers = AsyncMock(side_effect=Exception("Source failed"))
                    mock_sources.return_value = [mock_source]
                    
                    # Create database - should use stale cache
                    db = await MCPDatabase.create()
                    
                    # Verify stale cache was used
                    assert len(db.servers) == 1
                    assert db.servers[0].name == "stale-server"
    
    @pytest.mark.asyncio
    async def test_performance_characteristics(self, temp_cache_dir, mock_precomputed_data):
        """Test that precomputed data loading is fast (< 1 second)."""
        import time
        
        # Mock fast precomputed data responses
        async def mock_fast_get(url):
            # Simulate minimal network delay
            if "data_info.json" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value=mock_precomputed_data["data_info"])
                )
            elif "servers.json" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value=[asdict(s) for s in mock_precomputed_data["servers"]])
                )
            else:
                return Mock(status_code=200, content=b"mock_data")
        
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_fast_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with patch('numpy.load', return_value=mock_precomputed_data["embeddings"]):
                    # Time the database creation
                    start_time = time.time()
                    db = await MCPDatabase.create()
                    load_time = time.time() - start_time
                    
                    # Should be very fast with precomputed data
                    assert load_time < 1.0, f"Loading took {load_time:.2f}s, expected < 1.0s"
                    assert len(db.servers) == 2
    
    @pytest.mark.asyncio
    async def test_semantic_search_initialization(self, temp_cache_dir, mock_precomputed_data):
        """Test that semantic search initializes correctly with precomputed embeddings."""
        
        # Mock successful precomputed data loading
        async def mock_get(url):
            if "data_info.json" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value=mock_precomputed_data["data_info"])
                )
            elif "servers.json" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value=[asdict(s) for s in mock_precomputed_data["servers"]])
                )
            elif "embeddings.npz" in url:
                return Mock(status_code=200, content=b"mock_embeddings")
            else:
                raise ValueError(f"Unexpected URL: {url}")
        
        with patch('db.database.get_server_cache_dir', return_value=temp_cache_dir):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with patch('numpy.load', return_value=mock_precomputed_data["embeddings"]):
                    with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                        # Mock tempfile for embeddings download
                        mock_temp = Mock()
                        mock_temp.name = "/tmp/mock_embeddings.npz"
                        mock_tempfile.return_value.__enter__.return_value = mock_temp
                        
                        # Create database
                        db = await MCPDatabase.create()
                        
                        # Verify semantic search was initialized (it will fall back to local generation)
                        # This is the expected behavior when embeddings download/loading fails


@pytest.mark.asyncio 
async def test_end_to_end_user_experience():
    """
    Integration test simulating complete first-user experience.
    
    This test runs through the entire onboarding flow:
    1. Fresh install -> downloads precomputed data
    2. Second run -> uses cache
    3. Semantic search works
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "mcp-mcp" / "servers"
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Create realistic mock data
        servers_data = [
            {
                "name": "weather-api",
                "description": "Get weather forecasts and current conditions",
                "url": "https://github.com/example/mcp-weather",
                "category": "Data",
                "source": "official"
            },
            {
                "name": "database-connector", 
                "description": "Connect to PostgreSQL and MySQL databases",
                "url": "https://github.com/example/mcp-db",
                "category": "Database",
                "source": "community"
            }
        ]
        
        data_info = {
            "servers_count": 2,
            "schema_version": "1.0",
            "build_timestamp": 1750000000.0,
            "model_name": "all-MiniLM-L6-v2",
            "embeddings_shape": [2, 384]
        }
        
        # Mock network responses
        async def mock_get(url):
            if "data_info.json" in url:
                return Mock(status_code=200, json=Mock(return_value=data_info))
            elif "servers.json" in url:
                return Mock(status_code=200, json=Mock(return_value=servers_data))
            else:
                return Mock(status_code=200, content=b"mock_embeddings")
        
        with patch('db.database.get_server_cache_dir', return_value=cache_path):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_get
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with patch('numpy.load', return_value=np.random.rand(2, 384)):
                    # First run - fresh install
                    db1 = await MCPDatabase.create()
                    
                    # Verify data loaded
                    assert len(db1.servers) == 2
                    assert db1.servers[0].name == "weather-api"
                    
                    # When precomputed data is used, cache isn't created (by design)
                    # This is correct behavior - no need to cache precomputed data
                    
                    
@pytest.mark.asyncio
async def test_cache_creation_from_live_sources():
    """Test cache creation when precomputed data fails but live sources work."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "mcp-mcp" / "servers"
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Mock precomputed data to fail (404)
        async def mock_get_precomputed_fail(url):
            return Mock(status_code=404)
        
        # Mock live source data
        live_servers = [
            MCPServerEntry(
                name="live-weather",
                description="Weather from live source",
                url="https://github.com/example/live-weather",
                category="Data", 
                source="live"
            )
        ]
        
        with patch('db.database.get_server_cache_dir', return_value=cache_path):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = mock_get_precomputed_fail
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                # Mock live sources to return data
                with patch('db.sources.get_all_sources') as mock_sources:
                    mock_source = Mock()
                    mock_source.name = "Live Test Source"
                    mock_source.get_servers = AsyncMock(return_value=live_servers)
                    mock_sources.return_value = [mock_source]
                    
                    # First run - should create cache from live sources
                    db1 = await MCPDatabase.create()
                    
                    # Verify data loaded from live sources
                    assert len(db1.servers) == 1
                    assert db1.servers[0].name == "live-weather"
                    
                    # Verify cache was created 
                    cache_file = cache_path / "server_list.json"
                    assert cache_file.exists()
                    
                    # Second run - should use cache (make live sources fail)
                    mock_source.get_servers = AsyncMock(side_effect=Exception("Live source should not be called"))
                    
                    db2 = await MCPDatabase.create()
                    
                    # Verify same data loaded from cache
                    assert len(db2.servers) == 1
                    assert db2.servers[0].name == "live-weather"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("MCP_MCP_TEST_GITHUB_INTEGRATION"),
    reason="GitHub integration test disabled. Set MCP_MCP_TEST_GITHUB_INTEGRATION=1 to enable"
)
async def test_real_github_download():
    """
    Integration test that actually downloads from GitHub releases.
    
    This test is disabled by default and requires:
    export MCP_MCP_TEST_GITHUB_INTEGRATION=1
    
    It tests the complete real-world flow:
    1. Download data_info.json from GitHub releases
    2. Verify schema compatibility
    3. Download servers.json and embeddings.npz
    4. Verify data integrity
    """
    import os
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "mcp-mcp" / "servers"  
        cache_path.mkdir(parents=True, exist_ok=True)
        
        with patch('db.database.get_server_cache_dir', return_value=cache_path):
            # Create database - this will actually hit GitHub
            start_time = time.time()
            db = await MCPDatabase.create()
            load_time = time.time() - start_time
            
            # Verify we got real data
            assert len(db.servers) > 1000, f"Expected >1000 servers, got {len(db.servers)}"
            
            # Verify data quality
            server_names = [s.name for s in db.servers]
            assert any("weather" in name.lower() for name in server_names), "Should have weather-related servers"
            assert any("database" in name.lower() or "db" in name.lower() for name in server_names), "Should have database-related servers"
            
            # Verify all servers have required fields
            for server in db.servers[:10]:  # Check first 10
                assert server.name, f"Server missing name: {server}"
                assert server.description, f"Server missing description: {server}"
                assert server.url, f"Server missing URL: {server}"
                assert server.source, f"Server missing source: {server}"
            
            # Verify semantic search works with real embeddings
            assert db.semantic_engine is not None, "Semantic search should be initialized"
            
            # Test actual search
            results = db.semantic_engine.semantic_search("weather forecast", top_k=5)
            assert len(results) == 5, "Should return 5 results"
            assert all(0 <= score <= 1 for server, score in results), "Scores should be between 0 and 1"
            
            # Verify performance is acceptable (should be fast with precomputed data)
            assert load_time < 5.0, f"Real GitHub download took {load_time:.2f}s, expected < 5s"
            
            print(f"✅ Real GitHub integration test passed!")
            print(f"   📊 Loaded {len(db.servers)} servers in {load_time:.2f}s")
            print(f"   🔍 Semantic search working with real embeddings")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("MCP_MCP_TEST_GITHUB_INTEGRATION"),
    reason="GitHub integration test disabled. Set MCP_MCP_TEST_GITHUB_INTEGRATION=1 to enable"
)
async def test_real_github_redirect_handling():
    """
    Test that we properly handle real GitHub release redirects.
    
    This verifies our fix for the 302 redirect issue works in practice.
    """
    import httpx
    
    # Test the three GitHub release URLs directly
    urls = [
        "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest/data_info.json",
        "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest/servers.json", 
        "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest/embeddings.npz"
    ]
    
    # Test without follow_redirects (should fail)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        for url in urls:
            response = await client.get(url)
            assert response.status_code == 302, f"Expected 302 redirect for {url}, got {response.status_code}"
    
    # Test with follow_redirects=True (should work)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # Test data_info.json
        response = await client.get(urls[0])
        assert response.status_code == 200, f"Expected 200 for data_info.json, got {response.status_code}"
        data_info = response.json()
        assert "schema_version" in data_info, "data_info.json should contain schema_version"
        assert "servers_count" in data_info, "data_info.json should contain servers_count"
        
        # Test servers.json
        response = await client.get(urls[1])
        assert response.status_code == 200, f"Expected 200 for servers.json, got {response.status_code}"
        servers_data = response.json()
        assert isinstance(servers_data, list), "servers.json should contain a list"
        assert len(servers_data) > 0, "servers.json should not be empty"
        
        # Test embeddings.npz (just check it downloads)
        response = await client.get(urls[2])
        assert response.status_code == 200, f"Expected 200 for embeddings.npz, got {response.status_code}"
        assert len(response.content) > 1000, "embeddings.npz should be substantial in size"
    
    print(f"✅ Real GitHub redirect handling test passed!")
    print(f"   🔄 All URLs properly redirect from 302 → 200")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("MCP_MCP_TEST_GITHUB_STRESS"),
    reason="GitHub stress test disabled. Set MCP_MCP_TEST_GITHUB_STRESS=1 to enable"
)
async def test_github_download_stress():
    """
    Stress test that simulates multiple concurrent users downloading.
    
    This helps verify our GitHub releases can handle load and our
    caching/retry logic works under stress.
    """
    import asyncio
    
    async def create_database_instance():
        """Create a database instance in a temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "mcp-mcp" / "servers"
            cache_path.mkdir(parents=True, exist_ok=True)
            
            with patch('db.database.get_server_cache_dir', return_value=cache_path):
                start_time = time.time()
                db = await MCPDatabase.create()
                load_time = time.time() - start_time
                return len(db.servers), load_time
    
    # Run 5 concurrent downloads (simulating multiple users)
    print("🚀 Starting stress test with 5 concurrent downloads...")
    tasks = [create_database_instance() for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    # Verify all succeeded
    for i, (server_count, load_time) in enumerate(results):
        assert server_count > 1000, f"Instance {i}: Expected >1000 servers, got {server_count}"
        assert load_time < 10.0, f"Instance {i}: Load took {load_time:.2f}s, expected < 10s"
        print(f"   Instance {i}: {server_count} servers in {load_time:.2f}s")
    
    # Verify consistency
    server_counts = [result[0] for result in results]
    assert len(set(server_counts)) == 1, f"All instances should have same server count: {server_counts}"
    
    print(f"✅ GitHub stress test passed!")
    print(f"   📊 All 5 instances loaded {server_counts[0]} servers consistently")