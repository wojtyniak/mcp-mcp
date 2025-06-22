# MCP-MCP Server MVP - Product Requirements Document

## Executive Summary

### Problem Statement
Claude Code (and other AI assistants) often encounters situations where it needs tools that aren't currently available. For example, it might need to check domain availability, lookup weather data, or access a specific API. Currently, there's no way to dynamically discover and use MCP servers on-demand.

### Solution
A MCP-MCP (meta-mcp) Server that acts as a tool discovery and provisioning service. When an AI needs a capability, it can ask the MCP-MCP Server, which will:
1. Search for appropriate MCP servers across multiple sources (GitHub, npm, PyPI, etc.)
2. Build and run the server in a Docker container
3. Proxy requests to the containerized server

### MVP Success Criteria
- Successfully discover MCP servers from at least 3 different sources
- Build and run any MCP server in a Docker container
- Proxy MCP protocol between client and containerized servers
- Support MCP servers written in any language

## Core Use Case Examples

**User**: Claude Code  
**Scenario**: Need to check domain availability while helping a user

```
PoC:
1. Claude Code calls: find_and_use_tool("check domain availability for example.com")
2. Meta-MCP searches:
   - Provided MCP servers list
   - GitHub for repos with "mcp" and "whois/domain" 
3. Finds "mcp-whois" on GitHub
4. Checks tool definitions for that MCP Server
5. Offers them to the MCP client for confirmation (if not confirmed, go back to step 2)
6. Offers configuration string to the MCP client so user can manually configure it
MVP:
6. Runs the MCP server in a container if applicable (e.g. it doesn't require access to filesystem)
7. Offers configuration string to the MCP client so user can manually configure it
```

**User**: Claude Desktop Client
**Scenario**: Need to plan travel to a new city and requires data from multiple sources.
```
PoC
1. Claude Desktop Client calls: find_and_use_tool("find weather data for Tokyo, Japan, for the next 7 days")
2. Meta-MCP searches:
   - Provided MCP servers list
   - GitHub for repos with "mcp" and "weather" 
3. Finds "mcp-weather" on GitHub
4. Checks tool definitions for that MCP Server
5. Offers them to the MCP client for confirmation (if not confirmed, go back to step 2)
6. Offers configuration string to the MCP client so user can manually configure it
MVP:
6. Runs the MCP server in a container if applicable (e.g. it doesn't require access to filesystem)
7. Offers configuration string to the MCP client so user can manually configure it
```

## Functional Requirements for PoC

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
1. **MCP Server Lists** - Awesome Lists - PoC
    - Lists with URL to MCP servers sources and their descriptions

1. **GitHub** - Most MCP servers are likely here - MVP
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

### Phase 1: PoC (Proof of Concept)
1. **Single Source Discovery**
   - Download and search provided MCP server lists
   - Basic keyword matching for capability discovery

2. **API Confirmation Flow**
   - Show MCP client the tools offered by discovered servers
   - Get confirmation from MCP client to proceed
   - Handle denial and search for alternative servers

3. **Configuration String Generation**
   - Generate JSON config for Claude Desktop Client
   - Generate command string for Claude Code
   - Manual configuration workflow

### Phase 2: MVP Foundation
1. **Multi-Source Discovery**
   - GitHub API integration for MCP server search
   - Basic ranking by stars/relevance
   - AI-powered capability matching

2. **Docker Infrastructure**
   - Docker API integration
   - Basic Dockerfile generation for Python/Node.js
   - Container lifecycle management

### Phase 3: MVP Core
1. **MCP Protocol Proxy**
   - Handle stdio transport to containers
   - Request routing to appropriate servers
   - Connection failure handling

2. **Server Execution**
   - Build and run discovered servers in containers
   - Environment variable configuration
   - Container isolation and cleanup

### Phase 4: MVP Polish
1. **Server Management**
   - Track running containers
   - Cache built images
   - Clean up idle containers
   - List available servers

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