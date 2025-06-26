# MCP-MCP: Meta-MCP Server

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![MCP-MCP: An MCP server that helps discover other MCP servers](assets/matryoshka.jpg)

**MCP-MCP** is a Meta-MCP Server that acts as a tool discovery and provisioning service for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). When an AI assistant needs a capability that isn't currently available, it can ask MCP-MCP to discover and suggest appropriate MCP servers from a comprehensive database of over a thousand servers aggregated from multiple curated sources.

Think of it as a "phone book" for MCP servers - one tool to find all other tools.

## Motivation

**Agents Just Wanna Have Tools** 

- **Agents know what they need**: AI assistants can clearly articulate requirements like "check domain availability" or "get weather data"
- **Web search isn't always enough**: Generic search results don't always provide realtime data
- **CLI tools require setup**: Many tools need complex installation, configuration, and API keys - agents have to repeat this setup every single time they need to complete a task
- **MCP servers are scattered**: Great tools exist but discovering them requires manual research across GitHub, forums, and documentation

Why make agents (and users) hunt for tools when we can bring the tools to them?

## Quick Start

### Install via uvx (Recommended)

```bash
uvx mcp-mcp
```

This installs and runs the MCP-MCP server directly via uvx.

## Claude Desktop Configuration

Add MCP-MCP to your Claude Desktop configuration file:

### Configuration File Location:
- **macOS**: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
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

## Claude Code Configuration

Add MCP-MCP to your Claude Code configuration file:

```bash
claude mcp add mcp-mcp uvx mcp-mcp
```
## Usage Examples

Once configured, you can ask Claude Desktop to discover MCP servers using natural language:

- **"Find me an MCP server for weather data"**
- **"I need a server for checking domain availability"** 
- **"Search for MCP servers related to stock market data"**
- **"What MCP servers are available for web scraping?"**

## Development

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [direnv](https://direnv.net/) (optional, for automatic environment setup)

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/mcp-mcp.git
cd mcp-mcp

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the server
uv run main.py
```

### Development Mode

For development with HTTP transport:

```bash
# HTTP mode (accessible at http://localhost:8000)
uv run main.py --http

# Custom host/port
uv run main.py --http --host 0.0.0.0 --port 3000
```

### Building

```bash
# Build package
uv build

# Test local installation
uvx --from ./dist/mcp_mcp-0.1.0-py3-none-any.whl mcp-mcp
```

## Command Line Options

```bash
mcp-mcp --help
```

| Option | Description | Default |
|--------|-------------|---------|
| `--transport {stdio,http}` | Transport method | `stdio` |
| `--http` | Use HTTP transport | - |
| `--host HOST` | Host for HTTP transport | `localhost` |
| `--port PORT` | Port for HTTP transport | `8000` |

## Testing

```bash
# Run all unit tests (fast, no network)
uv run pytest

# Run specific module tests
uv run pytest db/ -v

# Run GitHub integration tests (optional, requires network)
MCP_MCP_TEST_GITHUB_INTEGRATION=1 uv run pytest db/test_precomputed_data_workflow.py::test_real_github_download -v -s

# Run with coverage
uv run pytest --cov=db
```

**Integration Tests**: Set `MCP_MCP_TEST_GITHUB_INTEGRATION=1` to test real GitHub downloads and verify the complete first-user onboarding experience. These tests ensure users get fast startup (< 5 seconds) with 1296+ servers.

## Roadmap

### Current Status: PoC Complete
- ✅ Multi-source discovery (3 curated MCP server lists)
- ✅ Semantic search with precomputed embeddings
- ✅ Configuration string generation
- ✅ FastMCP integration

### Next: MVP Foundation
- [ ] Multi-source discovery (GitHub API)
- [ ] Docker integration for server execution
- [ ] MCP protocol proxy
- [ ] Server lifecycle management

### Future Enhancements
- [ ] Private registry support
- [ ] Dependency resolution
- [ ] Performance monitoring
- [ ] Web UI for server management

## Contributing

We welcome contributions! Please see our [development setup](#development) and:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow Python 3.13+ best practices
- Add tests for new functionality
- Update documentation as needed
- Use semantic commit messages

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) team at Anthropic
- Open source MCP server maintainers and contributors
- MCP Server Lists:
  - [Official MCP Servers](https://github.com/modelcontextprotocol/servers)
  - [Punkpeye's Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers)
  - [Appcypher's Awesome MCP Servers](https://github.com/appcypher/awesome-mcp-servers)

---

**Made with ❤️ for the MCP ecosystem**