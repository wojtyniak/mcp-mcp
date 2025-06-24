from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from mcp.server.fastmcp import FastMCP, Context

from agents import AgentManager
from mcp_db import MCPDatabase, MCPServerEntry  # noqa: E402
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


mcp = FastMCP("MCP-MCP", lifespan=app_lifespan)


@mcp.tool()
async def find_mcp_server(description: str, example_question: str | None = None, ctx: Context = None) -> dict:
    """
    Look for an MCP server that can provide the requested functionality.

    Example usage:
    find_mcp_server(
        description="Find weather forecast for a given location",
        example_question="What is the weather in Tokyo, Japan, for the next 7 days?")

    find_mcp_server(
        description="Check domain availability",
        example_question="Is example.com available?")

    Args:
        description: Natural language description of needed functionality
        example_question: Example question that would use the capability
    """
    logger.info(f"Searching for MCP server: {description}")
    
    # Access the global database instance
    if _global_mcp_db is None:
        return {
            "status": "error",
            "message": "MCP database not initialized"
        }
    
    mcp_db = _global_mcp_db
    
    # Build search query from description and example
    search_query = description
    if example_question:
        search_query += " " + example_question
    
    # Search for relevant servers
    results = mcp_db.search(search_query)
    
    if not results:
        return {
            "status": "not_found",
            "message": f"No MCP servers found for: {description}",
            "suggestions": "Try a different search term or check the available server categories"
        }
    
    # Return top result with configuration options
    top_server = results[0]
    
    response = {
        "status": "found",
        "server": {
            "name": top_server.name,
            "description": top_server.description,
            "url": top_server.url,
            "category": top_server.category
        },
        "configuration": _generate_configuration_strings(top_server),
        "alternatives": []
    }
    
    # Include up to 3 alternative servers
    for alt_server in results[1:4]:
        response["alternatives"].append({
            "name": alt_server.name,
            "description": alt_server.description,
            "url": alt_server.url,
            "category": alt_server.category
        })
    
    logger.info(f"Found {len(results)} servers, returning: {top_server.name}")
    return response


def _generate_configuration_strings(server: MCPServerEntry) -> dict:
    """Generate configuration strings for different MCP clients."""
    
    # For servers hosted on GitHub, we need to determine how to run them
    if "github.com" in server.url:
        # Extract repository info from GitHub URL
        # Example: https://github.com/modelcontextprotocol/servers/tree/main/src/fetch
        parts = server.url.replace("https://github.com/", "").split("/")
        if len(parts) >= 2:
            repo_owner = parts[0]
            repo_name = parts[1]
            
            # Determine the server path for MCP servers repository
            if "modelcontextprotocol/servers" in server.url:
                if "/src/" in server.url:
                    server_path = server.url.split("/src/")[1]
                    server_name = server_path.split("/")[0]
                else:
                    server_name = server.name.lower().replace(" ", "-")
            else:
                server_name = repo_name
            
            # Generate configurations
            claude_desktop_config = {
                "mcpServers": {
                    server.name.lower().replace(" ", "-"): {
                        "command": "uvx",
                        "args": [f"mcp-{server_name}"] if server_name != server.name.lower().replace(" ", "-") else [f"mcp-{server.name.lower().replace(' ', '-')}"],
                        "env": {}
                    }
                }
            }
            
            claude_code_config = f"uvx mcp-{server_name}"
            
            return {
                "claude_desktop": claude_desktop_config,
                "claude_code": claude_code_config,
                "manual_setup_url": server.url,
                "note": "Configuration assumes the server is installable via uvx/npm. Check the server's README for specific setup instructions."
            }
    
    return {
        "manual_setup_url": server.url,
        "note": "Please refer to the server's documentation for setup instructions."
    }


@mcp.tool()
async def greet(name: str):
    logger.debug("greeting %s", name)
    result = await AgentManager.send_message("greeter", f"greet {name}")
    logger.debug(f"result: {result}")
    return result


def main():
    import sys
    # Use stdio transport for testing, http for production
    transport = "stdio" if len(sys.argv) > 1 and sys.argv[1] == "--stdio" else "streamable-http"
    
    try:
        mcp.run(transport=transport)
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        raise e


if __name__ == "__main__":
    main()
