# Claude Code Project Journal for MCP-MCP 

# Note format
## Date MM/DD/YYYY
### Item 1
- Details

# Journal

## 06/24/2025
### Simplified Agent Session Management  
- **Problem**: Attempted complex session reuse logic but service needs to be idempotent
- **Solution**: Applied YAGNI/KISS/DRY principles to dramatically simplify session handling
- **Key Changes**:
  - Eliminated manual UUID generation: `f"{user_id}-{uuid.uuid4()}"` → let ADK handle session ID creation
  - Removed over-engineered SessionManager class (100+ lines of unnecessary code)
  - Moved session logic into `AgentManager.send_message()` class method for better cohesion
  - Added `APP_NAME = "mcp-mcp"` constant to avoid repeating app name parameter
  - Each tool call now gets fresh session for true idempotent behavior
- **API Evolution**:
  ```python
  # Before: 2-step process with repeated app name
  runner = AgentManager.get_agent_runner("greeter", "mcp-mcp") 
  result = await send_message(runner, f"greet {name}")
  
  # After: Clean single method call
  result = await AgentManager.send_message("greeter", f"greet {name}")
  ```
- **Core Insight**: Don't build session "management" when you just need session creation
- **Langfuse Integration Issue**: LiteLLM callbacks don't work with Google ADK's LiteLlm wrapper - version compatibility issue between LiteLLM 1.73.0 and Langfuse 3.0.3

## 06/23/2025
### Implemented MCP Server List Parser
- Created `parse_mcp_server_list()` function in search.py:14
- Parses markdown format from MCP servers repository README
- Handles 4 server categories: reference, archived, official, community
- Uses regex to extract server name, description, URL, and category
- Handles image tags and normalizes whitespace
- Converts relative URLs to absolute GitHub URLs
- Added comprehensive pytest test suite in search_test.py with 4 test cases
- All tests passing ✅

### Configured Logging System
- Set up custom logging configuration with Rich for colored output
- Created `settings.py` with Pydantic BaseSettings for configuration management
- Environment variable support: `MCPMCP_DEBUG=true` enables debug logging
- Implemented hierarchical logger structure (`mcp-mcp.*`) to avoid conflicts with FastMCP/Uvicorn
- Set `propagate=False` to prevent duplicate log messages
- Different libraries use different log formats (Rich with/without timestamps, plain Uvicorn format)

### FastMCP Integration
- Discovered FastMCP lifespan context manager executes lazily on first request, not startup
- Configured FastMCP server with custom settings and lifespan manager
- Added MCPDatabase integration with async initialization in lifespan


