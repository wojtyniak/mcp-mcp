from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP


@dataclass
class AppContext:
    pass


@asynccontextmanager
async def app_lifespan(app: FastMCP):
    print("Starting up...")
    yield
    print("Shutting down...")


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
