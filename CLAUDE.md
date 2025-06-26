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
No special environment configuration required. Uses standard Python/uv project setup.

## Project Architecture

See @PRD.md for the product requirements and architecture documentation.

**MCP-MCP (Meta-MCP) Server** - A tool discovery and provisioning service for MCP servers that helps AI assistants dynamically find, containerize, and use MCP servers on-demand.

**Core Technology Stack:**
- Python 3.13+ with uv package manager
- Key dependencies: `httpx`, `mcp`, `sentence-transformers`, `rich`, `pydantic-settings`
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
- Find MCP server tool with README fetching (`main.py:find_mcp_tool()`)
- Comprehensive pytest test suite (`db/test_database.py`)
- Custom logging with Rich and Pydantic settings (`settings.py`)
- FastMCP server integration with lifespan management (`main.py`)
- **README Integration**: Automatic fetching of documentation from GitHub repositories
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
def find_mcp_tool(description: str, example_question: str | None = None) -> dict:
    """Look for an MCP server that can provide the requested functionality.
    
    Returns server details with complete README documentation for setup instructions.
    """
```

**Discovery Sources (planned):**
1. Curated MCP server lists
2. GitHub repositories (search: `mcp language:python/javascript/go stars:>5`)
3. Package registries (npm, PyPI)
4. Direct Git repository URLs

## Schema Versioning

**Current Schema**: v1.0 with fields: `name`, `description`, `url`, `category`, `source`
**Data Size**: ~2MB (small enough for fast fallback)

**Simple Strategy**:
- ✅ v1.x data: Use precomputed data (instant startup)
- ❌ v2.x+ data: Fall back to live GitHub sources (3-second startup)

**Safety Guarantees (Tested & Verified)**: 
- **Never breaks user process**: v1.x client + v2.x data = automatic fallback (no crash)
- **Graceful degradation**: Malformed entries are skipped, process continues  
- **Always functional**: Live GitHub sources ensure system always works
- **Multiple safety layers**: Schema check → Data validation → Individual entry parsing → Exception handling
- **User experience**: Incompatible data = 3-second startup instead of instant (barely noticeable)

**Why This Works**: For our small data size, downloading fresh from GitHub is fast and reliable. No complex migration needed.

**Implementation**: `db/schema_versions.py` - simple compatibility check with fallback

## Security Considerations

- No API keys required for core functionality
- Docker containers planned for MCP server isolation
- No privileged container execution
- README content fetched over HTTPS with timeout protection
- Schema validation prevents malformed data from breaking the system

## Testing

**Framework:** pytest is configured and working

**Testing Strategy:**
- **Unit tests**: Fast, mocked, always run (db/test_database.py, test_precomputed_data_workflow.py)
- **Integration tests**: Real GitHub downloads, behind environment flags
- **Critical path focus**: First-user onboarding experience thoroughly tested

**Key Test Files:**
- `db/test_database.py` - Core database functionality tests
- `db/test_precomputed_data_workflow.py` - Complete onboarding flow tests with optional real GitHub integration

**Integration Test Flags:**
- `MCP_MCP_TEST_GITHUB_INTEGRATION=1` - Enable real GitHub download tests
- `MCP_MCP_TEST_GITHUB_STRESS=1` - Enable concurrent user simulation tests

**Performance Targets (Verified):**
- Fresh install: < 5 seconds (real GitHub download + 1296 servers + semantic search)
- Cache hits: < 1 second
- Concurrent users: 5 simultaneous downloads succeed consistently

**Technical Testing Notes:**
- GitHub releases use 302 redirects to S3 (requires follow_redirects=True in httpx)
- Schema versioning tested for both compatible and incompatible scenarios
- Cache behavior: only created when precomputed data fails (not when it succeeds)
- Semantic search tested with real embeddings and similarity scoring

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
- README integration provides complete setup documentation

**FastMCP Behavior:**
- The `lifespan` context manager only executes on the first request to the server, not during startup
- This is lazy initialization - server starts listening immediately but doesn't run lifespan until first tool call

**Known Issues:**
- **Semantic Search Quality**: Some generic queries (e.g. "Tool for programmatically testing a website") return irrelevant results due to semantic model limitations. Affects queries that don't use specific technical terms. Specific technical queries work well (e.g. "browser automation", "playwright testing").

**Missing Infrastructure (to be added):**
- Code formatting/linting (ruff, black)
- Type checking (mypy)
- CI/CD automation
- Docker configuration for the meta-server itself

**Key Files:**

- `README.md` - Comprehensive project documentation, installation, and usage guide
- `PRD.md` - Product requirements and architecture documentation
- `TASKS.md` - Tasks to be completed
- `pyproject.toml` - Project dependencies, scripts, and pytest configuration
- `main.py` - FastMCP server entry point with CLI interface
- `settings.py` - Application settings and logging configuration
- `db/database.py` - MCP server discovery and parsing logic
- `db/semantic_search.py` - Semantic search using sentence-transformers
- `db/schema_versions.py` - Schema versioning and compatibility framework
- `db/test_database.py` - Test suite for database functionality
- `db/test_precomputed_data_workflow.py` - Comprehensive onboarding workflow tests with optional GitHub integration

## Development Philosophy

- You Are Not Gonna Need It (YAGNI)
- Keep It Simple Stupid (KISS)
- Don't Repeat Yourself (DRY)

## Dependency Management

- Always use `uv add` to add dependencies

## MCP Workflow Management

- Use mcp to: edit commit messages; split commits; merge commits; do the usual commit management and cleanup expected from a good developer