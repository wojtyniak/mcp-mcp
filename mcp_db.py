from dataclasses import dataclass

import httpx

from settings import app_logger

logger = app_logger.getChild(__name__)

SERVER_LIST_URL = "https://raw.githubusercontent.com/modelcontextprotocol/servers/refs/heads/main/README.md"


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

    @classmethod
    async def create(cls) -> "MCPDatabase":
        mcp_db = cls(servers=[])
        await mcp_db._load_servers()
        return mcp_db

    async def _load_servers(self) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.get(SERVER_LIST_URL)
            mcp_server_list = response.text
        self.servers = parse_mcp_server_list(mcp_server_list)
        logger.debug(f"Loaded {len(self.servers)} servers")

    def search(self, query: str) -> list[MCPServerEntry]:
        """Search for MCP servers with improved keyword matching and relevance scoring."""
        if not query.strip():
            return []
        
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
    
    def _calculate_relevance_score(self, server: MCPServerEntry, query_lower: str, query_words: set[str]) -> float:
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
                    if len(name_word) >= 3 and (query_word in name_word or name_word in query_word):
                        score += 5
                for desc_word in desc_words:
                    if len(desc_word) >= 3 and (query_word in desc_word or desc_word in query_word):
                        score += 2
        
        # Category boost for reference servers (only if there's already some content match)
        if score > 0:  # Only apply category boost if there's already a content match
            if server.category == "reference":
                score += 5
            elif server.category == "official":
                score += 3
        
        return score
