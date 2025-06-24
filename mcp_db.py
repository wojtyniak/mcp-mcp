import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import httpx

from settings import app_logger

logger = app_logger.getChild(__name__)

SERVER_LIST_URL = "https://raw.githubusercontent.com/modelcontextprotocol/servers/refs/heads/main/README.md"
SERVER_CACHE_TTL = 3 * 60 * 60  # 3 hours in seconds

if TYPE_CHECKING:
    from semantic_search import SemanticSearchEngine


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
                    )
                )

    return servers


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
        """Load servers from cache if fresh, otherwise download and cache."""
        # Try loading from cache first
        cached_content = self._load_cached_server_list()
        if cached_content is not None:
            logger.debug("Using cached server list")
            self.servers = parse_mcp_server_list(cached_content)
            logger.debug(f"Loaded {len(self.servers)} servers from cache")
            return
        
        # Cache miss or expired - download fresh data
        logger.info("Downloading fresh server list...")
        async with httpx.AsyncClient() as client:
            response = await client.get(SERVER_LIST_URL)
            mcp_server_list = response.text
        
        # Save to cache
        self._save_server_list_to_cache(mcp_server_list)
        
        self.servers = parse_mcp_server_list(mcp_server_list)
        logger.debug(f"Loaded {len(self.servers)} servers from remote")
    
    def _load_cached_server_list(self) -> Optional[str]:
        """Load server list from cache if it exists and is fresh."""
        cache_path = get_server_cache_path()
        
        if not cache_path.exists():
            return None
        
        try:
            # Check if cache is still fresh
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age > SERVER_CACHE_TTL:
                logger.debug(f"Server cache expired ({cache_age:.0f}s > {SERVER_CACHE_TTL}s)")
                return None
            
            # Load cached data
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return cache_data.get('content')
            
        except Exception as e:
            logger.warning(f"Failed to load cached server list: {e}")
            # Delete corrupted cache
            cache_path.unlink(missing_ok=True)
            return None
    
    def _save_server_list_to_cache(self, content: str) -> None:
        """Save server list content to cache."""
        cache_path = get_server_cache_path()
        
        try:
            cache_data = {
                'content': content,
                'timestamp': time.time(),
                'url': SERVER_LIST_URL
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False)
            
            logger.debug(f"Saved server list to cache: {cache_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save server list to cache: {e}")

    async def _initialize_semantic_search(self) -> None:
        """Initialize semantic search engine with fallback to keyword-only search."""
        try:
            from semantic_search import SemanticSearchEngine

            logger.info("Initializing semantic search engine...")
            self.semantic_engine = SemanticSearchEngine()
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
