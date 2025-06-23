from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from mcp.server.fastmcp import FastMCP

from agents import AgentManager, send_message
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


@mcp.tool()
async def greet(name: str):
    logger.debug("greeting %s", name)
    runner = AgentManager.get_agent_runner("template", "mcp-mcp")
    if runner is None:
        raise ValueError("Runner is None")
    logger.debug(f"sending message to agent {runner.agent.name}")
    result = await send_message(runner, f"greet {name}")
    logger.debug(f"result: {result}")
    return result


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
