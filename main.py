import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from mcp.server.fastmcp import FastMCP

from mcp_db import MCPDatabase  # noqa: E402
from settings import app_logger

logger = app_logger.getChild(__name__)


@dataclass
class AppContext:
    mcp_db: MCPDatabase


@asynccontextmanager
async def app_lifespan(_: FastMCP) -> AsyncGenerator[AppContext]:
    logger.info("Loading MCP database...")
    mcp_db = await MCPDatabase.create()
    logger.info("MCP database loaded")
    try:
        yield AppContext(mcp_db=mcp_db)
    finally:
        pass


mcp = FastMCP("MCP-MCP", lifespan=app_lifespan)


def main():
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        raise e


if __name__ == "__main__":
    main()
