"""
Multi-source MCP server discovery system.

This module provides an abstract base class for MCP server sources and 
concrete implementations for different sources like official repositories
and awesome lists.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urljoin

import httpx

from .database import MCPServerEntry
from settings import app_logger

logger = app_logger.getChild(__name__)


class ServerSource(ABC):
    """Abstract base class for MCP server sources."""
    
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
    
    @abstractmethod
    async def fetch(self) -> str:
        """Fetch the raw content from the source."""
        pass
    
    @abstractmethod
    def parse(self, content: str) -> list[MCPServerEntry]:
        """Parse the content and extract MCP server entries."""
        pass
    
    async def get_servers(self) -> list[MCPServerEntry]:
        """Get all servers from this source."""
        try:
            logger.info(f"Fetching servers from {self.name}")
            content = await self.fetch()
            servers = self.parse(content)
            logger.info(f"Found {len(servers)} servers from {self.name}")
            return servers
        except Exception as e:
            logger.error(f"Failed to get servers from {self.name}: {e}")
            return []


class OfficialMCPSource(ServerSource):
    """Official MCP servers from modelcontextprotocol/servers repository."""
    
    def __init__(self):
        super().__init__(
            name="Official MCP Servers",
            url="https://raw.githubusercontent.com/modelcontextprotocol/servers/refs/heads/main/README.md"
        )
    
    async def fetch(self) -> str:
        """Fetch the official MCP servers README."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            return response.text
    
    def parse(self, content: str) -> list[MCPServerEntry]:
        """Parse the official MCP servers README format."""
        servers = []
        lines = content.split("\n")
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
                server = self._parse_server_line(line, current_category)
                if server:
                    servers.append(server)

        return servers
    
    def _parse_server_line(self, line: str, category: str) -> Optional[MCPServerEntry]:
        """Parse a single server line from the official format."""
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

            return MCPServerEntry(
                name=name,
                description=description,
                url=url,
                category=category,
                source="official"
            )
        return None


class PunkpeyeAwesomeSource(ServerSource):
    """Awesome MCP servers from punkpeye/awesome-mcp-servers repository."""
    
    def __init__(self):
        super().__init__(
            name="Punkpeye Awesome MCP Servers",
            url="https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
        )
    
    async def fetch(self) -> str:
        """Fetch the punkpeye awesome servers README."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            return response.text
    
    def parse(self, content: str) -> list[MCPServerEntry]:
        """Parse the punkpeye awesome servers format."""
        servers = []
        lines = content.split("\n")
        current_category = None
        
        for line in lines:
            line = line.strip()
            
            # Detect category headers (format: ## 🔗 Category Name)
            category_match = re.match(r"^##\s*[\w\s]*?\s*(.+?)(?:\s*\(.*\))?$", line)
            if category_match and not line.startswith("### "):
                # Extract category name, clean up emoji and extra text
                category_text = category_match.group(1)
                # Remove emojis and normalize category name
                current_category = re.sub(r"[^\w\s-]", "", category_text).strip().lower().replace(" ", "-")
                continue
            
            # Parse server entries
            if line.startswith("- ") and current_category:
                server = self._parse_server_line(line, current_category)
                if server:
                    servers.append(server)
        
        return servers
    
    def _parse_server_line(self, line: str, category: str) -> Optional[MCPServerEntry]:
        """Parse a single server line from punkpeye format."""
        # Format: - [emoji icon] [Name](url) - Description
        # Also handle format with language/deployment icons
        
        # Remove leading "- " and normalize
        content = line[2:].strip()
        
        # Extract GitHub URL and name
        url_match = re.search(r"\[([^\]]+)\]\((https://github\.com/[^)]+)\)", content)
        if not url_match:
            return None
        
        name = url_match.group(1)
        url = url_match.group(2)
        
        # Extract description (text after the link and optional " - ")
        description_start = url_match.end()
        description_part = content[description_start:].strip()
        
        # Remove leading " - " if present
        if description_part.startswith(" - "):
            description_part = description_part[3:].strip()
        elif description_part.startswith("- "):
            description_part = description_part[2:].strip()
        
        # Clean up description (remove emoji, normalize whitespace)
        description = re.sub(r"[^\w\s.,!?()-]", "", description_part).strip()
        if not description:
            description = f"MCP server for {category}"
        
        return MCPServerEntry(
            name=name,
            description=description,
            url=url,
            category=category,
            source="punkpeye-awesome"
        )


class AppcypherAwesomeSource(ServerSource):
    """Awesome MCP servers from appcypher/awesome-mcp-servers repository."""
    
    def __init__(self):
        super().__init__(
            name="Appcypher Awesome MCP Servers", 
            url="https://raw.githubusercontent.com/appcypher/awesome-mcp-servers/main/README.md"
        )
    
    async def fetch(self) -> str:
        """Fetch the appcypher awesome servers README."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            return response.text
    
    def parse(self, content: str) -> list[MCPServerEntry]:
        """Parse the appcypher awesome servers format."""
        servers = []
        lines = content.split("\n")
        current_category = None
        
        for line in lines:
            line = line.strip()
            
            # Detect category headers
            if line.startswith("## ") and not line.startswith("### "):
                # Extract category name
                category_text = line[3:].strip()
                # Clean up and normalize category name
                current_category = re.sub(r"[^\w\s-]", "", category_text).strip().lower().replace(" ", "-")
                continue
            
            # Parse server entries  
            if line.startswith("- ") and current_category:
                server = self._parse_server_line(line, current_category)
                if server:
                    servers.append(server)
        
        return servers
    
    def _parse_server_line(self, line: str, category: str) -> Optional[MCPServerEntry]:
        """Parse a single server line from appcypher format."""
        # Format: - <img...> [Name](url) - Description
        
        # Remove leading "- " and any img tags
        content = line[2:].strip()
        content = re.sub(r"<img[^>]*?>", "", content).strip()
        
        # Extract GitHub URL and name
        url_match = re.search(r"\[([^\]]+)\]\((https://github\.com/[^)]+)\)", content)
        if not url_match:
            return None
        
        name = url_match.group(1)
        url = url_match.group(2)
        
        # Extract description
        description_start = url_match.end()
        description_part = content[description_start:].strip()
        
        # Remove leading " - " if present
        if description_part.startswith(" - "):
            description_part = description_part[3:].strip()
        elif description_part.startswith("- "):
            description_part = description_part[2:].strip()
        
        # Use description or generate one
        description = description_part if description_part else f"MCP server for {category}"
        
        return MCPServerEntry(
            name=name,
            description=description,
            url=url,
            category=category,
            source="appcypher-awesome"
        )


def get_all_sources() -> list[ServerSource]:
    """Get all available server sources."""
    return [
        OfficialMCPSource(),
        PunkpeyeAwesomeSource(),
        AppcypherAwesomeSource(),
    ]