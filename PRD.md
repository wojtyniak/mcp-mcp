# MCP-MCP Server MVP - Product Requirements Document

## Executive Summary

### Problem Statement
Claude Code (and other AI assistants) often encounters situations where it needs tools that aren't currently available. For example, it might need to check domain availability, lookup weather data, or access a specific API. Currently, there's no way to dynamically discover and use MCP servers on-demand.

### Solution
A MCP-MCP (meta-mcp) Server that acts as a tool discovery and provisioning service. When an AI needs a capability, it can ask the MCP-MCP Server, which will:
1. Search for appropriate MCP servers across multiple sources (GitHub, npm, PyPI, etc.)
2. Build and run the server in a Docker container
3. Proxy requests to the containerized server

### MVP Success Criteria ✅ ACHIEVED
- ✅ Successfully discover MCP servers from 3 different sources (comprehensive unique server coverage)
- ✅ Semantic search with sub-second response times using precomputed embeddings
- ✅ Production-ready distribution via uvx/pipx with automated releases
- ✅ Security hardened with origin validation middleware
- ✅ Comprehensive test coverage and documentation

### Future Enhancements (Beyond MVP)
- Build and run any MCP server in a Docker container
- Proxy MCP protocol between client and containerized servers
- Support automatic MCP servers execution for any language

## Core Use Case Examples

**User**: Claude Code  
**Scenario**: Need to check domain availability while helping a user

```
Current MVP:
1. Claude Code calls: find_mcp_tool("check domain availability for example.com")
2. Meta-MCP searches across 3 curated sources with comprehensive server database using semantic search
3. Finds relevant servers like "mcp-whois" with complete documentation  
4. Returns server details with README installation instructions
5. User manually configures Claude Desktop/Code with provided configuration

Future Enhancement:
6. Automatically containerize and run the MCP server
7. Proxy MCP protocol requests seamlessly
```

**User**: Claude Desktop Client
**Scenario**: Need to plan travel to a new city and requires data from multiple sources.
```
Current MVP:
1. Claude Desktop Client calls: find_mcp_tool("find weather data for Tokyo, Japan, for the next 7 days")
2. Meta-MCP searches comprehensive server database using semantic similarity matching
3. Finds weather-related servers with complete setup documentation
4. Returns server details with configuration instructions for Claude Desktop
5. User adds server to Claude Desktop configuration and restarts

Future Enhancement:
6. Automatically provision and run weather server in container
7. Seamlessly proxy weather requests without user setup
```

## MVP Functional Requirements ✅ ACHIEVED

### 1. Single Source Discovery
- Download and search the provided list of MCP servers

### 2. API confirmation
- Show the MCP client the tools offered by the MCP server
- Get confirmation from the MCP client to use the tools
- In case of denial, find another MCP server and offer it to the MCP client

### 3. Configuration string
- Offer configuration string to the MCP client so user can manually configure it
- Two common configuration strings: json for Claude Desktop Client and cmd string for Claude Code

## Functional Requirements for MVP

### 1. Multi-Source Discovery
- Search GitHub for MCP servers (using GitHub API)
- Basic ranking by stars/downloads/relevance
- AI-powered matching of capability to server

### 2. Docker-based Execution
- Generate Dockerfile if not present
- Build Docker images for discovered servers
- Wrap servers using only stdio as the transport into a command line tool or a HTTP server
- Run containers with proper isolation
- Environment variables for configuration, API keys, etc.

### 3. MCP Protocol Proxy
- Handle stdio and HTTP transports
- Route requests to appropriate container
- Manage container lifecycle
- Handle connection failures gracefully

### 4. Server Management
- Track running containers
- Cache built images
- Clean up idle containers
- List available servers
- Offer basic web UI for managing servers

## MCP Tools Exposed by them mcp-mcp Server

```python
# Tools exposed by Meta-MCP Server

def find_mcp_server(description: str, example_question: str | None = None) -> dict:
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
```

## Discovery Strategy

### Source Prioritization
1. **MCP Server Lists** - Curated Awesome Lists - ✅ IMPLEMENTED
    - Official MCP servers list from ModelContextProtocol
    - Punkpeye/awesome-mcp-servers community collection
    - Appcypher/awesome-mcp-servers community collection

2. **GitHub** - Live API Integration - Future Enhancement
   - Search: `mcp language:python/javascript/go stars:>5`
   - Check README for MCP mentions

4. **Direct URLs** - future
   - Support direct GitHub/GitLab URLs
   - Support arbitrary Git repositories

### Ranking Algorithm - future
- Matching the description provided by the client with the description of the MCP server
- Matching the example question provided by the client with the example question of the MCP server
- GitHub stars / npm downloads (normalized)
- Last update recency
- Keyword match score
- Has Dockerfile bonus

## Docker Integration

### Dockerfile Generation - MVP
For servers without Dockerfiles, generate based on language:

```dockerfile
# Python example
FROM python:3.13
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
RUN uv tool install {{tool_name}}
CMD ["{{ tool_name }}"]
...
```
```dockerfile
# Node.js example  
FROM node:current
WORKDIR /app
RUN npm install -g {{tool_name}}
CMD ["{{tool_name}}"]
```

## Security Considerations

### Container Isolation
- No privileged containers
- Read-only root filesystem where possible - future

### Code Trust - future
- Display source and trust indicators
- Warn about unverified sources
- Allow whitelist/blacklist configuration
- No automatic execution without confirmation (override for AI)

## Implementation Constraints

### Technology Stack
- Language: Python 3.13+
- MCP SDK: Python implementation (https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#running-the-standalone-mcp-development-tools)
- Container: Docker API
- Discovery: GitHub API, httpx, web search 

### Simplifications for MVP
- No authentication to registries (use public APIs)
- Basic Dockerfile generation (may fail for complex projects)
- Simple process-based proxy (no advanced routing)
- No distributed operation (single instance)
- No UI (MCP tools only)

## Development Phases

### Phase 1: MVP Complete ✅
1. **Multi-Source Discovery ✅**
   - 3 curated MCP server sources with comprehensive unique server coverage
   - Semantic search using sentence-transformers for accurate matching
   - Precomputed embeddings for sub-second startup performance

2. **Production Distribution ✅**
   - uvx/pipx installation for end users
   - GitHub Actions automation for data updates
   - Schema versioning with graceful fallback

3. **Security & Quality ✅**
   - Origin validation middleware preventing DNS rebinding attacks
   - Comprehensive test suite (65+ tests)
   - Production hardening with localhost-only restrictions

4. **Documentation & UX ✅**
   - Complete README with installation and usage guides
   - Development workflow with justfile commands
   - Integration guides for Claude Desktop and Claude Code

### Phase 2: Advanced Features (Beyond MVP)
1. **Container Integration**
   - Docker API integration for server execution
   - Automatic Dockerfile generation for discovered servers
   - Container lifecycle management and cleanup

2. **MCP Protocol Proxy**
   - Request routing between clients and containerized servers
   - Handle stdio and HTTP transports seamlessly
   - Advanced connection management and error handling

3. **Live Discovery**
   - GitHub API integration for real-time server discovery
   - Package registry integration (npm, PyPI)
   - Dynamic ranking and relevance scoring

## Validation Criteria

- Successfully discover and run MPC servers in different scenarios
  - Weather forecast
  - Domain availability
  - Stock market data
  - Transit information
  - Item ordering/shopping
- All servers properly sandboxed in containers
- Claude Code can use discovered tools without errors
- Containers are cleaned up properly

## Future Enhancements

- **Private Registries**: Support authenticated sources
- **Caching Layer**: Pre-built images for popular servers
- **Dependency Resolution**: Handle complex server dependencies
- **Multi-Container**: Servers that need multiple containers
- **Performance**: Connection pooling, warm containers
- **Observability**: Metrics, logs aggregation