# Nix MCP Server

A Model Context Protocol (MCP) server for working with Nix derivations, expressions, and flakes.

## Features

This MCP server provides tools for:

- **Building** Nix derivations and flakes
- **Evaluating** Nix expressions
- **Querying** flake outputs
- **Checking** flake validity
- **Searching** packages in nixpkgs and other flakes

All operations write detailed logs to `/tmp` and return structured results without overwhelming the LLM with build output.

## Installation

### Using Nix Flakes

```bash
# Run directly
nix run github:yourusername/nix-mcp

# Install to profile
nix profile install github:yourusername/nix-mcp

# Add to your system/home-manager configuration
{
  inputs.nix-mcp.url = "github:yourusername/nix-mcp";
  # ...
}
```

### Local Development

```bash
# Enter development shell
nix develop

# Run the server
python -m nix_mcp.server
```

## Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "nix": {
      "command": "nix",
      "args": ["run", "/path/to/nix-mcp"]
    }
  }
}
```

Or if installed via `nix profile`:

```json
{
  "mcpServers": {
    "nix": {
      "command": "nix-mcp"
    }
  }
}
```

## Available Tools

### nix_build

Build a Nix derivation or flake.

**Parameters:**
- `flake_ref` (required): Flake reference (e.g., `.#default`, `nixpkgs#hello`)
- `extra_args` (optional): Additional arguments to pass to nix build

**Returns:**
- `success`: Boolean indicating build success
- `store_path`: Path in `/nix/store` (only on success)
- `log_file`: Path to detailed build logs in `/tmp`

**Example:**
```json
{
  "flake_ref": ".#default",
  "extra_args": ["--no-link"]
}
```

### nix_eval

Evaluate a Nix expression or flake attribute.

**Parameters:**
- `flake_ref` (required): Expression or flake attribute to evaluate
- `raw` (optional): Output raw result without quotes
- `json` (optional): Output as JSON

**Returns:**
- `success`: Boolean indicating evaluation success
- `result`: Evaluation result
- `log_file`: Path to logs

**Example:**
```json
{
  "flake_ref": ".#packages.x86_64-linux.default.version",
  "raw": true
}
```

### nix_flake_show

Show the outputs of a flake.

**Parameters:**
- `flake_ref` (optional): Flake reference (default: `.`)

**Returns:**
- `success`: Boolean
- `outputs`: Structured flake output information
- `log_file`: Path to logs

**Example:**
```json
{
  "flake_ref": "nixpkgs"
}
```

### nix_flake_check

Check a Nix flake for errors.

**Parameters:**
- `flake_ref` (optional): Flake reference (default: `.`)

**Returns:**
- `success`: Boolean indicating if flake is valid
- `log_file`: Path to logs with detailed error information

**Example:**
```json
{
  "flake_ref": "."
}
```

### nix_search

Search for Nix packages.

**Parameters:**
- `query` (required): Search query
- `flake_ref` (optional): Flake to search in (default: `nixpkgs`)

**Returns:**
- `success`: Boolean
- `results`: Search results object
- `count`: Number of results found
- `log_file`: Path to logs

**Example:**
```json
{
  "query": "python3",
  "flake_ref": "nixpkgs"
}
```

## Log Files

All operations write detailed logs to `/tmp/nix-mcp-{operation}-{timestamp}.log`. These files contain:
- The exact command executed
- Exit code
- Full stdout and stderr output

The agent can read these files if detailed error information is needed.

## Development

### Building

```bash
nix build
```

### Testing

```bash
# Enter dev shell
nix develop

# Run the server
python -m nix_mcp.server

# Test with MCP inspector (if available)
npx @modelcontextprotocol/inspector python -m nix_mcp.server
```

## License

MIT
