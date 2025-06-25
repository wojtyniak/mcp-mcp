# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Journal

Keep development journal in @JOURNAL.md. Update it after each major change.

## Note-Taking Guidelines

- When asked to take notes: 1) Fill out @JOURNAL.md; 2) Add only the most important information to @CLAUDE.md 

## Development Setup

This project uses Python 3.13+ with `uv` as the package manager and `direnv` for environment management.

**Essential Commands:**
- `uv sync` - Install/update dependencies (automatically triggered by direnv)
- `uv add <package>` - Add a dependency
- `uv run pytest` - Run unit tests
- `uv run main.py` - Run the application
- `uv build` - Build package for distribution
- `uvx mcp-mcp` - Install and run via uvx (end-user command)

**Environment Configuration:**
The project uses `.envrc` with direnv for automatic environment setup including:
- Langfuse observability integration (host: `http://docks.srv.0x89.net:3000`)
- API keys loaded from macOS keychain
- OpenTelemetry tracing configuration

## Project Architecture

See @PRD.md for the product requirements and architecture documentation.

**MCP-MCP (Meta-MCP) Server** - A tool discovery and provisioning service for MCP servers that helps AI assistants dynamically find, containerize, and use MCP servers on-demand.

**Core Technology Stack:**
- Python 3.13+ with uv package manager
- Key dependencies: `litellm`, `langfuse`, `google-adk`
- Planned: Docker for server containerization, GitHub API for discovery

**Development Phases (from PRD.md):**
1. **PoC**: Single-source discovery with manual configuration
2. **MVP Foundation**: Multi-source discovery (GitHub API) with Docker integration
3. **MVP Core**: MCP protocol proxy with automated container execution
4. **MVP Polish**: Full server management with cleanup and monitoring

**Key Architectural Patterns:**
- **Discovery Pattern**: Search multiple sources (GitHub, MCP lists, registries) for appropriate MCP servers
- **Containerization**: Build and run discovered servers in Docker containers for isolation
- **Proxy Pattern**: Route MCP protocol requests between clients and containerized servers
- **Multi-language Support**: Generate Dockerfiles for Python, Node.js, and other MCP servers

## Current Implementation Status

**PoC COMPLETE ✅:**
- MCP server list parser (`db/database.py:parse_mcp_server_list()`)
- Semantic search with sentence-transformers (`db/semantic_search.py`)
- Find MCP server tool with configuration generation (`main.py:find_mcp_server()`)
- Comprehensive pytest test suite (`db/test_database.py`)
- Custom logging with Rich and Pydantic settings (`settings.py`)
- FastMCP server integration with lifespan management (`main.py`)
- Agent session management with Google ADK (`agents/agents_manager.py`)
- **Production Distribution**: uvx/pipx installation, Claude Desktop integration
- **Comprehensive Documentation**: README.md with complete user/developer guide

**Next Phase - MVP Foundation:**
- Multi-source discovery (GitHub API integration)
- Docker integration for server execution
- MCP protocol proxy
- CI/CD pipeline

**Main Entry Point:** `main.py` - full FastMCP server with CLI interface

## MCP Protocol Integration

The server exposes this primary tool:
```python
def find_mcp_server(description: str, example_question: str | None = None) -> dict:
    """Look for an MCP server that can provide the requested functionality."""
```

**Discovery Sources (planned):**
1. Curated MCP server lists
2. GitHub repositories (search: `mcp language:python/javascript/go stars:>5`)
3. Package registries (npm, PyPI)
4. Direct Git repository URLs

## Security Considerations

- API keys stored in macOS keychain (not in code)
- Docker containers planned for MCP server isolation
- No privileged container execution
- Environment variables for configuration secrets

## Testing

**Framework:** pytest is configured and working

**Testing Patterns:**
- Test files live next to the modules they test (e.g., `db/test_database.py`)
- Test files follow `test_*.py` naming convention 
- Use pytest fixtures and assertions
- Import modules using relative imports: `from .database import MCPServerEntry`
- Test multiple scenarios: normal cases, edge cases, type validation
- Run tests with: `uv run pytest` (runs all tests) or `uv run pytest db/ -v` (specific module)

**Test Structure Example:**
```python
import pytest
from module import function_to_test

def test_function_basic_case():
    result = function_to_test(input_data)
    assert result == expected_output

def test_function_edge_case():
    result = function_to_test("")
    assert len(result) == 0
```

## Development Notes

**PyPI Distribution:**
- Automated versioning with setuptools-scm (git tags → package versions)
- PEP 440 compliant development versions (e.g., 0.0.1.dev16)
- 1Password CLI integration for secure API token management
- Ready for Test PyPI and production PyPI distribution

**MCP Protocol Compatibility:**
- All logging redirected to stderr (not stdout) to avoid interfering with stdin/stdout MCP communication
- Works properly with Claude Desktop and uvx installations
- Tool discovery description optimized for proactive AI agent usage

**FastMCP Behavior:**
- The `lifespan` context manager only executes on the first request to the server, not during startup
- This is lazy initialization - server starts listening immediately but doesn't run lifespan until first tool call

**Missing Infrastructure (to be added):**
- Code formatting/linting (ruff, black)
- Type checking (mypy)
- CI/CD automation
- Docker configuration for the meta-server itself

**Key Files:**

- `README.md` - Comprehensive project documentation, installation, and usage guide
- `PRD.md` - Product requirements and architecture documentation
- `TASKS.md` - Tasks to be completed
- `.envrc` - Environment configuration with API keys and observability setup
- `pyproject.toml` - Project dependencies, scripts, and pytest configuration
- `main.py` - FastMCP server entry point with CLI interface
- `db/database.py` - MCP server discovery and parsing logic
- `db/semantic_search.py` - Semantic search using sentence-transformers
- `db/test_database.py` - Test suite for database functionality

## Development Philosophy

- You Are Not Gonna Need It (YAGNI)
- Keep It Simple Stupid (KISS)
- Don't Repeat Yourself (DRY)

## Dependency Management

- Always use `uv add` to add dependencies