# mirth_connect_mcp

MCP server for NextGen Connect (Mirth) that exposes API operations as domain-grouped tools.

## Requirements

- Python 3.13+
- Reachable NextGen Connect API endpoint
- Credentials with API access

## Install

Recommended (global command available in PATH):

```bash
uv tool install mirth_connect_mcp
```

Alternative:

```bash
pip install mirth_connect_mcp
```

After install, the command is:

```bash
mirth-connect-mcp
```

## Environment variables

Required:

- `MIRTH_BASE_URL` (example: `https://localhost:8443/api`)
- `MIRTH_USERNAME`
- `MIRTH_PASSWORD`

Optional:

- `MIRTH_VERIFY_SSL` (`true` by default; set `false` for local self-signed certs)
- `MIRTH_TIMEOUT_SECONDS` (`30` by default)
- `MIRTH_OPENAPI_PATH` (defaults to bundled OpenAPI spec)

## Add to MCP clients

Use `stdio` transport for all client configs below.

### VS Code (MCP)

Open your VS Code MCP config (`mcp.json`) and add:

```json
{
	"servers": {
		"mirthNextgen": {
			"type": "stdio",
			"command": "mirth-connect-mcp",
			"env": {
				"MIRTH_BASE_URL": "https://localhost:8443/api",
				"MIRTH_USERNAME": "admin",
				"MIRTH_PASSWORD": "admin",
				"MIRTH_VERIFY_SSL": "false"
			}
		}
	}
}
```

### Cline

In Cline MCP settings, add this server entry:

```json
{
	"mcpServers": {
		"mirthNextgen": {
			"command": "mirth-connect-mcp",
			"args": [],
			"env": {
				"MIRTH_BASE_URL": "https://localhost:8443/api",
				"MIRTH_USERNAME": "admin",
				"MIRTH_PASSWORD": "admin",
				"MIRTH_VERIFY_SSL": "false"
			}
		}
	}
}
```

### Claude Desktop

In `claude_desktop_config.json`, add:

```json
{
	"mcpServers": {
		"mirthNextgen": {
			"command": "mirth-connect-mcp",
			"env": {
				"MIRTH_BASE_URL": "https://localhost:8443/api",
				"MIRTH_USERNAME": "admin",
				"MIRTH_PASSWORD": "admin",
				"MIRTH_VERIFY_SSL": "false"
			}
		}
	}
}
```

### Gemini CLI

In your Gemini CLI MCP config, add:

```json
{
	"mcpServers": {
		"mirthNextgen": {
			"command": "mirth-connect-mcp",
			"env": {
				"MIRTH_BASE_URL": "https://localhost:8443/api",
				"MIRTH_USERNAME": "admin",
				"MIRTH_PASSWORD": "admin",
				"MIRTH_VERIFY_SSL": "false"
			}
		}
	}
}
```

## Tool model

Built-in tools:

- `list_domains`
- `list_actions`
- One dispatch tool per OpenAPI domain/tag

Domain tool request envelope:

```json
{
	"action": "operationId",
	"path_params": {},
	"query": {},
	"body": {},
	"headers_override": {}
}
```


