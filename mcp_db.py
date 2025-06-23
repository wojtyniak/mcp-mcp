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

    def search(self, query: str) -> set[MCPServerEntry]:
        return {
            server
            for server in self.servers
            if query in server.name or query in server.description
        }
