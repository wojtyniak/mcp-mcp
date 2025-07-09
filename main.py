import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx
from mcp.server.fastmcp import Context, FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.exceptions import HTTPException

from db import MCPDatabase
from settings import app_logger

logger = app_logger.getChild(__name__)

# Global database instance
_global_mcp_db: MCPDatabase | None = None


@dataclass
class AppContext:
    mcp_db: MCPDatabase


@asynccontextmanager
async def app_lifespan(_: FastMCP) -> AsyncGenerator[AppContext]:
    global _global_mcp_db
    logger.info("Loading MCP database...")
    mcp_db = await MCPDatabase.create()
    _global_mcp_db = mcp_db  # Store globally for tool access
    logger.info("MCP database loaded")
    try:
        yield AppContext(mcp_db=mcp_db)
    finally:
        pass


class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Origin headers and prevent DNS rebinding attacks."""
    
    def __init__(self, app, allowed_hosts: list[str]):
        super().__init__(app)
        self.allowed_origins = set()
        
        # Generate allowed origins for both http and https
        for host in allowed_hosts:
            if host in ("localhost", "127.0.0.1"):
                # Add common ports for localhost
                for port in [8000, 8080, 3000, 5000]:
                    self.allowed_origins.add(f"http://{host}:{port}")
                    self.allowed_origins.add(f"https://{host}:{port}")
                # Also allow without port for default
                self.allowed_origins.add(f"http://{host}")
                self.allowed_origins.add(f"https://{host}")
            else:
                self.allowed_origins.add(f"http://{host}")
                self.allowed_origins.add(f"https://{host}")
    
    async def dispatch(self, request: Request, call_next):
        # Check Origin header if present
        origin = request.headers.get("origin")
        if origin is not None:
            if origin not in self.allowed_origins:
                logger.warning(f"Rejected request with invalid origin: {origin}")
                return Response(
                    content="Forbidden: Invalid origin header",
                    status_code=403,
                    headers={"Content-Type": "text/plain"}
                )
        
        # Check Host header as additional protection
        host = request.headers.get("host")
        if host is not None:
            # Extract hostname from host header (remove port if present)
            hostname = host.split(":")[0]
            # Allow localhost and 127.0.0.1 for local development
            if hostname not in ("localhost", "127.0.0.1"):
                logger.warning(f"Rejected request with invalid host: {host}")
                return Response(
                    content="Forbidden: Invalid host header", 
                    status_code=403,
                    headers={"Content-Type": "text/plain"}
                )
        
        return await call_next(request)


mcp = FastMCP("MCP-MCP", lifespan=app_lifespan)


async def _fetch_readme_content(server_url: str) -> str | None:
    """Fetch README content from a GitHub repository."""
    if "github.com" not in server_url:
        return None
    
    try:
        # Convert GitHub URL to raw content URL
        # Example: https://github.com/owner/repo/tree/main/path -> https://raw.githubusercontent.com/owner/repo/main/path/README.md
        parts = server_url.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            return None
            
        owner = parts[0]
        repo = parts[1]
        
        # Handle different URL formats
        if "/tree/" in server_url:
            # URL with specific path like: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
            tree_part = server_url.split("/tree/")[1]
            branch_and_path = tree_part.split("/", 1)
            branch = branch_and_path[0]
            path = branch_and_path[1] if len(branch_and_path) > 1 else ""
        else:
            # Simple repo URL
            branch = "main"
            path = ""
        
        # Try different README file names
        readme_names = ["README.md", "README.txt", "README", "readme.md", "readme.txt", "readme"]
        
        for readme_name in readme_names:
            if path:
                readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}/{readme_name}"
            else:
                readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{readme_name}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(readme_url)
                if response.status_code == 200:
                    logger.info(f"Found README: {readme_name}")
                    return response.text
        
        logger.info(f"No README found for {server_url}")
        return None
        
    except Exception as e:
        logger.warning(f"Failed to fetch README for {server_url}: {e}")
        return None


@mcp.tool()
async def find_mcp_tool(
    description: str, example_question: str | None = None, ctx: Context = None
) -> dict:
    """
    FIRST ACTION RULE: When a user requests functionality you don't currently have access to,
    immediately use find_mcp_tool before explaining limitations or suggesting workarounds.

    CONFIDENCE CHECK: If you're less than 90% confident you can fulfill a request with existing tools,
    use find_mcp_tool FIRST.

    IMMEDIATE SEARCH TRIGGERS:
    - Real-time data (weather, stocks, crypto, exchange rates, news)
    - Web scraping, browser automation, or content extraction
    - Complex calendar operations (recurring events, scheduling, meeting coordination)
    - File format conversions (PDF, video, audio, image processing)
    - External service integrations (email sending, SMS, webhooks, messaging platforms)
    - Database operations (SQL queries, data imports/exports, vector databases)
    - Domain/DNS/network tools (availability, WHOIS, ping, traceroute)
    - Social media APIs (posting, analytics, profile data)
    - Data analysis beyond basic calculations (statistical analysis, ML, visualization)
    - Geographic/mapping services (geocoding, routing, location data)
    - Cloud platform management (AWS, Azure, Kubernetes, infrastructure)
    - Authentication and security operations (OAuth, API keys, security scanning)
    - Version control beyond basic Git (advanced operations, repository management)
    - Communication platforms (Slack, Discord, Telegram integration)
    - Blockchain and cryptocurrency operations (wallet management, DeFi interactions)
    - Code execution in sandboxed environments
    - Voice/speech generation and processing
    - Project management and productivity tools integration
    - Art, culture, and museum database access
    - Customer data platform queries
    - Developer tooling: automated testing (Playwright, Selenium), debugging, profiling, performance analysis
    - Development environments: game engines (Godot, Unity), IDEs, simulators, device testing
    - Build and deployment: CI/CD pipelines, Docker containers, package management, infrastructure as code
    - Code quality: linting, formatting, static analysis, security scanning, code review automation
    - API development: testing, documentation generation, mock servers, API monitoring
    - Mobile development: iOS/Android tooling, app store integration, device farms
    - Monitoring and observability: APM, logging systems, error tracking, metrics collection
    - Any request involving "create", "manage", "integrate", "automate", "query", "scrape", "deploy", "test", "debug", "build", "monitor", or "connect to"

    WORKFLOW:
    User request → Check confidence → If <90% confident → Use find_mcp_tool → Present solution

    SUCCESS PATTERNS:
    User: "Create recurring calendar events"
    → Use find_mcp_tool for calendar integration (don't just create basic iCal)

    User: "What's the weather in Tokyo?"
    → Use find_mcp_tool for weather server (don't say "I can't access weather")

    User: "Check if example.com is available"
    → Use find_mcp_tool for domain checker (don't suggest manual checking)

    This tool searches a curated database of MCP servers and returns the complete README 
    documentation from the repository. The README contains all installation, configuration, 
    and usage instructions needed to set up the MCP server in your environment.

    IMPORTANT: After finding a server, read the provided README content carefully to understand:
    - Installation requirements (npm, uvx, pip, etc.)
    - Configuration steps for Claude Desktop or Claude Code
    - Required API keys or environment variables
    - Available tools and their usage

    Args:
        description: Natural language description of the functionality you need
        example_question: Example of how you would use this capability (helps with matching)
    """
    logger.info(f"Searching for MCP server: {description}")

    # Access the global database instance, initialize if needed
    global _global_mcp_db
    if _global_mcp_db is None:
        logger.info("Initializing MCP database for direct tool usage...")
        _global_mcp_db = await MCPDatabase.create()

    mcp_db = _global_mcp_db

    # Use just the description for semantic search (more focused)
    search_query = description

    # Search for relevant servers
    results = mcp_db.search(search_query)

    if not results:
        return {
            "status": "not_found",
            "message": f"No MCP servers found for: {description}",
            "suggestions": "Try a different search term or check the available server categories",
        }

    # Find the best server with README content
    primary_server = None
    primary_readme = None
    alternatives = []

    # Try to fetch README for top results until we find one with documentation
    for i, server in enumerate(results[:4]):  # Check top 4 results
        readme_content = await _fetch_readme_content(server.url)
        
        if primary_server is None:
            # First server becomes primary regardless of README
            primary_server = server
            primary_readme = readme_content
            
            # If first server has README, we're done with primary selection
            if readme_content:
                # Add remaining servers as alternatives without README
                for alt_server in results[1:4]:
                    alternatives.append({
                        "name": alt_server.name,
                        "description": alt_server.description,
                        "url": alt_server.url,
                        "category": alt_server.category,
                        "source": alt_server.source,
                        "readme": None,
                    })
                break
        else:
            # Add to alternatives
            alternatives.append({
                "name": server.name,
                "description": server.description,
                "url": server.url,
                "category": server.category,
                "source": server.source,
                "readme": None,
            })
            
            # If primary doesn't have README but this one does, promote it to primary
            if primary_readme is None and readme_content:
                # Demote current primary to alternatives
                alternatives.insert(0, {
                    "name": primary_server.name,
                    "description": primary_server.description,
                    "url": primary_server.url,
                    "category": primary_server.category,
                    "source": primary_server.source,
                    "readme": None,
                })
                
                # Promote this server to primary
                primary_server = server
                primary_readme = readme_content
                
                # Remove the newly promoted server from alternatives
                alternatives.pop()
                break

    # Fill alternatives up to 3 if we don't have enough
    if len(alternatives) < 3:
        start_idx = 1 if primary_server == results[0] else 2
        for alt_server in results[start_idx:4]:
            if len(alternatives) >= 3:
                break
            if alt_server != primary_server:
                alternatives.append({
                    "name": alt_server.name,
                    "description": alt_server.description,
                    "url": alt_server.url,
                    "category": alt_server.category,
                    "source": alt_server.source,
                    "readme": None,
                })

    response = {
        "status": "found",
        "server": {
            "name": primary_server.name,
            "description": primary_server.description,
            "url": primary_server.url,
            "category": primary_server.category,
            "source": primary_server.source,
            "readme": primary_readme,
        },
        "alternatives": alternatives[:3],  # Ensure max 3 alternatives
    }

    readme_status = "with README" if primary_readme else "without README"
    logger.info(f"Found {len(results)} servers, returning: {primary_server.name} ({readme_status})")
    return response




def main():
    import argparse
    import sys

    # Try to import version, fallback to unknown if not available
    try:
        from version import version as __version__
    except ImportError:
        __version__ = "unknown"

    parser = argparse.ArgumentParser(
        description="MCP-MCP: Meta-MCP Server for dynamic MCP server discovery"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"mcp-mcp {__version__}"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method (default: stdio for Claude Desktop compatibility)",
    )
    parser.add_argument(
        "--http",
        action="store_const",
        const="http",
        dest="transport",
        help="Use HTTP transport (equivalent to --transport http)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for HTTP transport (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)"
    )

    # Parse args, but handle case where no args provided (for uvx compatibility)
    try:
        args = parser.parse_args()
        transport = "streamable-http" if args.transport == "http" else "stdio"
    except SystemExit as e:
        if e.code == 0:  # Help was shown
            sys.exit(0)
        # For any parsing errors, default to stdio (uvx compatibility)
        transport = "stdio"
        args = None

    # Note: STDIO mode is designed for MCP client communication, not interactive use
    # To terminate STDIO mode: send EOF (Ctrl+D) or close stdin
    # For development/testing, use --http mode for easier Ctrl+C termination

    try:
        if transport == "streamable-http" and args:
            logger.info(f"Starting MCP-MCP server on {args.host}:{args.port}")
            
            # Security warning for non-localhost hosts
            if args.host not in ("localhost", "127.0.0.1"):
                logger.warning(f"⚠️  SECURITY WARNING: Binding to {args.host} exposes server to network!")
                logger.warning("⚠️  Origin validation will still restrict to localhost origins only.")
                logger.warning("⚠️  For security, use --host localhost (default) for local development.")
            
            # Add Origin validation middleware for security
            # Always restrict to localhost/127.0.0.1 regardless of --host argument
            app = mcp.streamable_http_app()
            app.add_middleware(OriginValidationMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
            logger.info("Added Origin validation middleware for security (localhost only)")
            
            # Build the middleware stack  
            app.build_middleware_stack()
            logger.info("Built middleware stack")
            
            # FastMCP handles host/port internally for HTTP transport
            mcp.run(transport=transport)
        else:
            logger.info("Starting MCP-MCP server with stdio transport")
            logger.info("Server is ready for MCP client connections via stdin/stdout")
            logger.info("To stop: send EOF (Ctrl+D) or close stdin")
            mcp.run(transport=transport)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise e


if __name__ == "__main__":
    main()
