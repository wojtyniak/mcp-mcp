# MCP-MCP Installation Guide

## Quick Start

### Install via uvx (Recommended)

```bash
uvx mcp-mcp
```

This installs and runs the MCP-MCP server directly via uvx.

### Install via pipx

```bash
pipx install mcp-mcp
mcp-mcp
```

## Claude Desktop Configuration

Add the following to your Claude Desktop configuration file:

### Location of config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### Configuration:

```json
{
  "mcpServers": {
    "mcp-mcp": {
      "command": "uvx",
      "args": ["mcp-mcp"]
    }
  }
}
```

### Alternative with pipx:

```json
{
  "mcpServers": {
    "mcp-mcp": {
      "command": "mcp-mcp"
    }
  }
}
```

## Usage

Once configured, you can ask Claude Desktop to:

- "Find me an MCP server for weather data"
- "I need a server for checking domain availability"
- "Search for MCP servers related to stock market data"

The MCP-MCP server will search through hundreds of available MCP servers and provide you with:
1. The best matching server
2. Installation instructions
3. Configuration strings for both Claude Desktop and Claude Code
4. Alternative servers if available

## Development Mode

For development with HTTP transport:

```bash
mcp-mcp --http
```

## Command Line Options

```bash
mcp-mcp --help
```

- `--transport {stdio,http}`: Choose transport method (default: stdio)
- `--http`: Use HTTP transport (equivalent to `--transport http`)
- `--host HOST`: Host for HTTP transport (default: localhost)
- `--port PORT`: Port for HTTP transport (default: 8000)

## Features

- **Semantic Search**: Uses AI-powered semantic search to understand your natural language queries
- **800+ Servers**: Searches through a comprehensive database of MCP servers
- **Smart Caching**: Fast responses with intelligent caching (3-hour server list cache, persistent embeddings cache)
- **Multiple Sources**: Discovers servers from official MCP repositories and community sources
- **Easy Configuration**: Provides ready-to-use configuration strings for both Claude Desktop and Claude Code