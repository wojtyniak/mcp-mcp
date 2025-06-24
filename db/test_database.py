from .database import MCPServerEntry, parse_mcp_server_list

mcp_server_list = """
# Model Context Protocol servers

This repository is a collection of *reference implementations* for the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP), as well as references
to community built servers and additional resources.

## 🌟 Reference Servers

These servers aim to demonstrate MCP features and the TypeScript and Python SDKs.

- **[Everything](src/everything)** - Reference / test server with prompts, resources, and tools
- **[Fetch](src/fetch)** - Web content fetching and conversion for efficient LLM usage

### Archived

The following reference servers are now archived and can be found at [servers-archived](https://github.com/modelcontextprotocol/servers-archived).

- **[AWS KB Retrieval](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/aws-kb-retrieval-server)** - Retrieval from AWS Knowledge Base using Bedrock Agent Runtime
- **[Brave Search](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/brave-search)** - Web and local search using Brave's Search API

## 🤝 Third-Party Servers

### 🎖️ Official Integrations

Official integrations are maintained by companies building production ready MCP servers for their platforms.

- <img height="12" width="12" src="https://www.21st.dev/favicon.ico" alt="21st.dev Logo" /> **[21st.dev Magic](https://github.com/21st-dev/magic-mcp)** - Create crafted UI components inspired by the best 21st.dev design engineers.

### 🌎 Community Servers

A growing set of community-developed and maintained servers demonstrates various applications of MCP across different domains.

> **Note:** Community servers are **untested** and should be used at **your own risk**. They are not affiliated with or endorsed by Anthropic.
- **[1Panel](https://github.com/1Panel-dev/mcp-1panel)** - MCP server implementation that provides 1Panel interaction.
- **[A2A](https://github.com/GongRzhe/A2A-MCP-Server)** - An MCP server that bridges the Model Context Protocol (MCP) with the Agent-to-Agent (A2A) protocol, enabling MCP-compatible AI assistants (like Claude) to seamlessly interact with A2A agents.
## 💬 Community

- [GitHub Discussions](https://github.com/orgs/modelcontextprotocol/discussions)

## ⭐ Support

If you find MCP servers useful, please consider starring the repository and contributing new servers or improvements!

---

Managed by Anthropic, but built together with the community. The Model Context Protocol is open source and we encourage everyone to contribute their own servers and improvements!
"""

mcp_server_list_parsed = [
    {
        "name": "Everything",
        "description": "Reference / test server with prompts, resources, and tools",
        "url": "https://github.com/modelcontextprotocol/servers/tree/main/src/everything",
        "category": "reference",
    },
    {
        "name": "Fetch",
        "description": "Web content fetching and conversion for efficient LLM usage",
        "url": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
        "category": "reference",
    },
    {
        "name": "AWS KB Retrieval",
        "description": "Retrieval from AWS Knowledge Base using Bedrock Agent Runtime",
        "url": "https://github.com/modelcontextprotocol/servers-archived/tree/main/src/aws-kb-retrieval-server",
        "category": "archived",
    },
    {
        "name": "Brave Search",
        "description": "Web and local search using Brave's Search API",
        "url": "https://github.com/modelcontextprotocol/servers-archived/tree/main/src/brave-search",
        "category": "archived",
    },
    {
        "name": "21st.dev Magic",
        "description": "Create crafted UI components inspired by the best 21st.dev design engineers.",
        "url": "https://github.com/21st-dev/magic-mcp",
        "category": "official",
    },
    {
        "name": "1Panel",
        "description": "MCP server implementation that provides 1Panel interaction.",
        "url": "https://github.com/1Panel-dev/mcp-1panel",
        "category": "community",
    },
    {
        "name": "A2A",
        "description": "An MCP server that bridges the Model Context Protocol (MCP) with the Agent-to-Agent (A2A) protocol, enabling MCP-compatible AI assistants (like Claude) to seamlessly interact with A2A agents.",
        "url": "https://github.com/GongRzhe/A2A-MCP-Server",
        "category": "community",
    },
]


def test_parse_mcp_server_list():
    parsed = parse_mcp_server_list(mcp_server_list)

    # Convert parsed MCPServerEntry objects to dicts for comparison
    parsed_dicts = [
        {
            "name": server.name,
            "description": server.description,
            "url": server.url,
            "category": server.category,
        }
        for server in parsed
    ]

    assert len(parsed) == len(mcp_server_list_parsed), (
        f"Expected {len(mcp_server_list_parsed)} servers, got {len(parsed)}"
    )

    for expected, actual in zip(mcp_server_list_parsed, parsed_dicts):
        assert expected == actual, f"Mismatch: expected {expected}, got {actual}"


def test_parse_mcp_server_list_returns_correct_types():
    parsed = parse_mcp_server_list(mcp_server_list)

    assert isinstance(parsed, list)
    for server in parsed:
        assert isinstance(server, MCPServerEntry)
        assert isinstance(server.name, str)
        assert isinstance(server.description, str)
        assert isinstance(server.url, str)
        assert isinstance(server.category, str)


def test_parse_empty_list():
    parsed = parse_mcp_server_list("")
    assert len(parsed) == 0


def test_parse_mcp_server_list_categories():
    parsed = parse_mcp_server_list(mcp_server_list)

    categories = {server.category for server in parsed}
    expected_categories = {"reference", "archived", "official", "community"}

    assert categories == expected_categories
