import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from collections import defaultdict

import httpx
import numpy as np

from settings import app_logger

# Import schema version management
from .schema_versions import (
    is_version_compatible, validate_data_format, get_compatibility_message, 
    CompatibilityLevel
)

logger = app_logger.getChild(__name__)

SERVER_LIST_URL = "https://raw.githubusercontent.com/modelcontextprotocol/servers/refs/heads/main/README.md"
SERVER_CACHE_TTL = 3 * 60 * 60  # 3 hours in seconds

# URLs for precomputed data from GitHub releases
GITHUB_RELEASE_BASE = "https://github.com/wojtyniak/mcp-mcp/releases/download/data-latest"
PRECOMPUTED_SERVERS_URL = f"{GITHUB_RELEASE_BASE}/servers.json"
PRECOMPUTED_EMBEDDINGS_URL = f"{GITHUB_RELEASE_BASE}/embeddings.npz"
PRECOMPUTED_DATA_INFO_URL = f"{GITHUB_RELEASE_BASE}/data_info.json"

if TYPE_CHECKING:
    from .semantic_search import SemanticSearchEngine


def get_server_cache_dir() -> Path:
    """Get cache directory for server lists following XDG standards."""
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        cache_base = Path(xdg_cache_home)
    else:
        cache_base = Path.home() / ".cache"
    
    cache_dir = cache_base / "mcp-mcp" / "servers"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_server_cache_path() -> Path:
    """Get path for cached server list."""
    return get_server_cache_dir() / "server_list.json"


@dataclass
class MCPServerEntry:
    name: str
    description: str
    url: str
    category: str
    source: str = "unknown"


def parse_mcp_server_list(mcp_server_list: str) -> list[MCPServerEntry]:
    import re

    servers = []
    lines = mcp_server_list.split("\n")
    current_category = None

    for line in lines:
        line = line.strip()

        # Detect category sections
        if line.startswith("## 🌟 Reference Servers"):
            current_category = "reference"
            continue
        elif line.startswith("### Archived"):
            current_category = "archived"
            continue
        elif line.startswith("### 🎖️ Official Integrations"):
            current_category = "official"
            continue
        elif line.startswith("### 🌎 Community Servers"):
            current_category = "community"
            continue

        # Parse server entries (lines starting with -)
        if line.startswith("- ") and current_category:
            # Handle different patterns:
            # - **[Name](url)** - Description
            # - <img...> **[Name](url)** - Description

            # Remove image tags if present
            clean_line = re.sub(r"<img[^>]*?>", "", line)
            clean_line = re.sub(r"\s+", " ", clean_line)  # Normalize whitespace
            clean_line = clean_line.strip()

            # Extract name, url, and description
            # Pattern: - **[Name](url)** - Description (with flexible spacing)
            match = re.search(
                r"-\s*\*\*\[([^\]]+)\]\(([^)]+)\)\*\*\s*-\s*(.+)", clean_line
            )
            if match:
                name = match.group(1)
                url = match.group(2)
                description = match.group(3)

                # Handle relative URLs by making them absolute GitHub URLs
                if url.startswith("src/"):
                    url = f"https://github.com/modelcontextprotocol/servers/tree/main/{url}"

                servers.append(
                    MCPServerEntry(
                        name=name,
                        description=description,
                        url=url,
                        category=current_category,
                        source="official"
                    )
                )

    return servers


def deduplicate_servers(all_servers: list[MCPServerEntry]) -> list[MCPServerEntry]:
    """
    Deduplicate servers by URL, merging descriptions from different sources.
    """
    # Group servers by URL
    servers_by_url = defaultdict(list)
    for server in all_servers:
        servers_by_url[server.url].append(server)
    
    deduplicated = []
    for url, server_list in servers_by_url.items():
        if len(server_list) == 1:
            # No duplicates for this URL
            deduplicated.append(server_list[0])
        else:
            # Merge duplicates - combine all unique descriptions
            primary_server = server_list[0]
            sources = [s.source for s in server_list]
            
            # Collect all unique descriptions
            descriptions = []
            for server in server_list:
                desc = server.description.strip()
                if desc and desc not in descriptions:
                    descriptions.append(desc)
            
            # Join descriptions with semicolon separator
            merged_description = "; ".join(descriptions)
            
            # Combine source information  
            unique_sources = list(set(sources))
            source_info = "+".join(sorted(unique_sources))
            
            deduplicated.append(MCPServerEntry(
                name=primary_server.name,
                description=merged_description,
                url=url,
                category=primary_server.category,
                source=source_info
            ))
            
            logger.debug(f"Merged {len(server_list)} entries for {primary_server.name} from sources: {unique_sources}")
    
    return deduplicated


@dataclass
class MCPDatabase:
    servers: list[MCPServerEntry]
    semantic_engine: Optional["SemanticSearchEngine"] = None

    @classmethod
    async def create(cls) -> "MCPDatabase":
        mcp_db = cls(servers=[])
        await mcp_db._load_servers()
        await mcp_db._initialize_semantic_search()
        return mcp_db

    async def _load_servers(self) -> None:
        """Load servers from multiple sources with caching and deduplication."""
        # Try loading from precomputed data first (fastest)
        precomputed_servers = await self._load_precomputed_servers()
        if precomputed_servers is not None:
            logger.info("Using precomputed server data from GitHub releases")
            self.servers = precomputed_servers
            logger.info(f"Loaded {len(self.servers)} servers from precomputed data")
            return
        
        # Try loading from cache second
        cached_servers = self._load_cached_servers()
        if cached_servers is not None:
            logger.debug("Using cached server list")
            self.servers = cached_servers
            logger.debug(f"Loaded {len(self.servers)} servers from cache")
            return
        
        # Cache miss or expired - download fresh data from all sources
        logger.info("Downloading fresh server lists from all sources...")
        
        # Import here to avoid circular imports
        from .sources import get_all_sources
        
        all_servers = []
        sources = get_all_sources()
        network_errors = []
        
        for source in sources:
            try:
                source_servers = await source.get_servers()
                all_servers.extend(source_servers)
                logger.info(f"Loaded {len(source_servers)} servers from {source.name}")
            except Exception as e:
                logger.warning(f"Failed to load from {source.name}: {e}")
                network_errors.append(f"{source.name}: {e}")
                # Continue with other sources
        
        # Check if we have network errors (some sources failed)
        if network_errors:
            # Check if we have stale cache data available
            stale_servers = self._load_cached_servers(allow_stale=True)
            if stale_servers is not None:
                # Prefer complete stale data over partial fresh data
                if not all_servers or len(stale_servers) > len(all_servers):
                    logger.info(f"Using stale cache with {len(stale_servers)} servers (better than {len(all_servers)} from partial sources)")
                    self.servers = stale_servers
                    return
                else:
                    logger.info(f"Fresh data from {len(all_servers)} servers is more complete than stale cache ({len(stale_servers)})")
        
        # If all sources failed and no servers loaded
        if not all_servers:
            # Try stale cache as last resort
            stale_servers = self._load_cached_servers(allow_stale=True)
            if stale_servers is not None:
                logger.warning(f"All sources failed, using stale cache with {len(stale_servers)} servers")
                self.servers = stale_servers
                return
            else:
                # No data available at all
                raise Exception(
                    f"Failed to load from all sources and no cache available. Errors: {'; '.join(network_errors)}"
                )
        
        # Deduplicate servers across sources
        self.servers = deduplicate_servers(all_servers)
        
        # Save consolidated servers to cache
        self._save_servers_to_cache(self.servers)
        
        logger.info(f"Total: {len(self.servers)} unique servers (from {len(all_servers)} raw entries)")
    
    async def _check_schema_compatibility(self) -> Optional[dict]:
        """Check if precomputed data schema is compatible with this client version."""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(PRECOMPUTED_DATA_INFO_URL)
                
                if response.status_code == 200:
                    data_info = response.json()
                    
                    # Validate data format
                    validation_error = validate_data_format(data_info)
                    if validation_error:
                        logger.warning(f"Invalid data format: {validation_error}")
                        return None
                    
                    schema_version = data_info.get("schema_version", "1.0")  # Default for legacy
                    compatibility = is_version_compatible(schema_version)
                    
                    # Log compatibility status
                    compat_message = get_compatibility_message(schema_version)
                    if compatibility == CompatibilityLevel.COMPATIBLE:
                        logger.debug(compat_message)
                        return data_info
                    else:
                        logger.info(compat_message)
                        return None  # Fall back to live sources
                        
                else:
                    logger.debug(f"Data info not available (HTTP {response.status_code})")
                    return None
                    
        except Exception as e:
            logger.debug(f"Could not check schema compatibility: {e}")
            return None
    
    async def _load_precomputed_servers(self) -> Optional[list[MCPServerEntry]]:
        """Load precomputed servers from GitHub releases with schema compatibility checking."""
        # Check schema compatibility first
        data_info = await self._check_schema_compatibility()
        if data_info is None:
            logger.info("Skipping precomputed data due to schema incompatibility")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                logger.debug("Attempting to download precomputed servers...")
                response = await client.get(PRECOMPUTED_SERVERS_URL)
                
                if response.status_code == 200:
                    servers_data = response.json()
                    servers = []
                    
                    for server_dict in servers_data:
                        try:
                            # Handle missing source field for backward compatibility
                            if 'source' not in server_dict:
                                server_dict['source'] = 'unknown'
                            servers.append(MCPServerEntry(**server_dict))
                        except Exception as e:
                            # If any server entry fails to parse, log and skip it
                            # Don't let one bad entry break the entire process
                            logger.warning(f"Skipping malformed server entry: {e}")
                            continue
                    
                    if not servers:
                        # If no servers could be parsed, fall back to live sources
                        logger.warning("No valid servers found in precomputed data, falling back to live sources")
                        return None
                    
                    logger.debug(f"Downloaded {len(servers)} precomputed servers (schema v{data_info.get('schema_version', 'unknown')})")
                    return servers
                else:
                    logger.debug(f"Precomputed servers not available (HTTP {response.status_code})")
                    return None
                    
        except Exception as e:
            logger.debug(f"Could not load precomputed servers: {e}")
            return None
    
    async def _load_precomputed_embeddings(self) -> Optional[np.ndarray]:
        """Load precomputed embeddings from GitHub releases with schema compatibility checking."""
        # Check schema compatibility first
        data_info = await self._check_schema_compatibility()
        if data_info is None:
            logger.info("Skipping precomputed embeddings due to schema incompatibility")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                logger.debug("Attempting to download precomputed embeddings...")
                response = await client.get(PRECOMPUTED_EMBEDDINGS_URL)
                
                if response.status_code == 200:
                    # Save to temporary file and load with numpy
                    temp_file = get_server_cache_dir() / "temp_precomputed_embeddings.npz"
                    temp_file.write_bytes(response.content)
                    
                    embeddings_data = np.load(temp_file)
                    embeddings = embeddings_data['embeddings']
                    
                    # Clean up temporary file
                    temp_file.unlink()
                    
                    logger.debug(f"Downloaded precomputed embeddings: {embeddings.shape} (schema v{data_info.get('schema_version', 'unknown')})")
                    return embeddings
                else:
                    logger.debug(f"Precomputed embeddings not available (HTTP {response.status_code})")
                    return None
                    
        except Exception as e:
            logger.debug(f"Could not load precomputed embeddings: {e}")
            return None
    
    def _load_cached_servers(self, allow_stale: bool = False) -> Optional[list[MCPServerEntry]]:
        """
        Load processed servers from cache if it exists and is fresh.
        
        Args:
            allow_stale: If True, return cached data even if expired (for network failures)
        """
        cache_path = get_server_cache_path()
        
        if not cache_path.exists():
            return None
        
        try:
            # Check if cache is still fresh
            cache_age = time.time() - cache_path.stat().st_mtime
            is_expired = cache_age > SERVER_CACHE_TTL
            
            if is_expired and not allow_stale:
                logger.debug(f"Server cache expired ({cache_age:.0f}s > {SERVER_CACHE_TTL}s)")
                return None
            
            # Load cached data
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Convert back to MCPServerEntry objects
            servers_data = cache_data.get('servers', [])
            servers = []
            for server_dict in servers_data:
                # Handle legacy cache format without source field
                if 'source' not in server_dict:
                    server_dict['source'] = 'unknown'
                servers.append(MCPServerEntry(**server_dict))
            
            if is_expired and allow_stale:
                logger.warning(
                    f"Using stale cached data ({cache_age:.0f}s old) due to network issues"
                )
            
            return servers
            
        except Exception as e:
            logger.warning(f"Failed to load cached servers: {e}")
            # Delete corrupted cache
            cache_path.unlink(missing_ok=True)
            return None
    
    def _save_servers_to_cache(self, servers: list[MCPServerEntry]) -> None:
        """Save processed servers to cache."""
        cache_path = get_server_cache_path()
        
        try:
            cache_data = {
                'servers': [asdict(server) for server in servers],
                'timestamp': time.time(),
                'version': 'multi-source-v1'
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved {len(servers)} servers to cache: {cache_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save servers to cache: {e}")

    async def _initialize_semantic_search(self) -> None:
        """Initialize semantic search engine with fallback to keyword-only search."""
        try:
            from .semantic_search import SemanticSearchEngine

            logger.info("Initializing semantic search engine...")
            self.semantic_engine = SemanticSearchEngine()
            
            # Try to load precomputed embeddings first
            precomputed_embeddings = await self._load_precomputed_embeddings()
            if precomputed_embeddings is not None:
                logger.info("Using precomputed embeddings from GitHub releases")
                await self.semantic_engine.initialize_with_precomputed_embeddings(
                    self.servers, precomputed_embeddings
                )
            else:
                logger.info("Generating embeddings locally...")
                await self.semantic_engine.initialize(self.servers)
            
            logger.info("Semantic search initialized successfully")

        except Exception as e:
            logger.warning(
                f"Failed to initialize semantic search, falling back to keyword-only: {e}"
            )
            self.semantic_engine = None

    def search(self, query: str) -> list[MCPServerEntry]:
        """
        Search for MCP servers using semantic similarity.
        Falls back to keyword search if semantic search is unavailable.
        """
        if not query.strip():
            return []

        # Try semantic search first
        if self.semantic_engine and self.semantic_engine.is_available():
            try:
                semantic_results = self.semantic_engine.semantic_search(
                    query, top_k=20, similarity_threshold=0.1
                )
                # Extract just the servers from (server, score) tuples
                return [server for server, score in semantic_results]

            except Exception as e:
                logger.warning(
                    f"Semantic search failed, falling back to keyword search: {e}"
                )
                return self._keyword_search(query)
        else:
            # Fallback to keyword-only search
            logger.debug("Using keyword-only search (semantic search unavailable)")
            return self._keyword_search(query)

    def _keyword_search(self, query: str) -> list[MCPServerEntry]:
        """Fallback keyword-based search with relevance scoring."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []

        for server in self.servers:
            score = self._calculate_relevance_score(server, query_lower, query_words)
            if score > 0:
                results.append((score, server))

        # Sort by relevance score (highest first) and return servers
        results.sort(key=lambda x: x[0], reverse=True)
        return [server for _, server in results]

    def _calculate_relevance_score(
        self, server: MCPServerEntry, query_lower: str, query_words: set[str]
    ) -> float:
        """Calculate relevance score for a server based on query."""
        score = 0.0

        name_lower = server.name.lower()
        desc_lower = server.description.lower()

        # Exact name match gets highest score
        if query_lower == name_lower:
            score += 100

        # Partial name match gets high score
        elif query_lower in name_lower:
            score += 50

        # Exact description match gets good score
        if query_lower in desc_lower:
            score += 30

        # Word-based scoring
        name_words = set(name_lower.split())
        desc_words = set(desc_lower.split())

        # Count exact word matches in name (higher weight)
        name_matches = len(query_words.intersection(name_words))
        score += name_matches * 20

        # Count exact word matches in description
        desc_matches = len(query_words.intersection(desc_words))
        score += desc_matches * 10

        # Partial word matches (fuzzy matching) - more restrictive
        for query_word in query_words:
            if len(query_word) >= 3:  # Only do fuzzy matching for words >= 3 chars
                for name_word in name_words:
                    if len(name_word) >= 3 and (
                        query_word in name_word or name_word in query_word
                    ):
                        score += 5
                for desc_word in desc_words:
                    if len(desc_word) >= 3 and (
                        query_word in desc_word or desc_word in query_word
                    ):
                        score += 2

        # Category boost for reference servers (only if there's already some content match)
        if score > 0:  # Only apply category boost if there's already a content match
            if server.category == "reference":
                score += 5
            elif server.category == "official":
                score += 3

        return score

    def get_search_info(self) -> dict:
        """Get information about the search capabilities."""
        info = {
            "total_servers": len(self.servers),
            "semantic_search_available": False,
            "search_mode": "keyword-only",
            "server_cache_info": self._get_server_cache_info(),
        }

        if self.semantic_engine:
            semantic_available = self.semantic_engine.is_available()
            info.update(
                {
                    "semantic_search_available": semantic_available,
                    "search_mode": "semantic" if semantic_available else "keyword-only",
                    "embeddings_cache_info": self.semantic_engine.get_cache_info(),
                }
            )

        return info
    
    def _get_server_cache_info(self) -> dict:
        """Get information about server list cache."""
        cache_path = get_server_cache_path()
        
        if not cache_path.exists():
            return {
                "cache_exists": False,
                "cache_path": str(cache_path),
            }
        
        try:
            cache_age = time.time() - cache_path.stat().st_mtime
            cache_size = cache_path.stat().st_size
            
            return {
                "cache_exists": True,
                "cache_path": str(cache_path),
                "cache_age_seconds": int(cache_age),
                "cache_age_hours": round(cache_age / 3600, 1),
                "cache_size_bytes": cache_size,
                "cache_fresh": cache_age <= SERVER_CACHE_TTL,
                "ttl_seconds": SERVER_CACHE_TTL,
            }
        except Exception as e:
            return {
                "cache_exists": True,
                "cache_path": str(cache_path),
                "error": str(e),
            }
