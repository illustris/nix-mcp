#!/usr/bin/env python3
"""Nix MCP Server - provides tools for working with Nix derivations, expressions, and flakes."""

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent


app = Server("nix-mcp")


def run_nix_command(
	args: list[str],
	log_prefix: str,
	capture_output: bool = True,
) -> tuple[bool, str, str]:
	"""
	Run a nix command and log output to /tmp.

	Args:
		args: Command arguments (including 'nix' as first element)
		log_prefix: Prefix for log filename
		capture_output: Whether to capture stdout/stderr

	Returns:
		Tuple of (success, stdout, log_file_path)
	"""
	timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
	log_file = Path(f"/tmp/nix-mcp-{log_prefix}-{timestamp}.log")

	try:
		result = subprocess.run(
			args,
			capture_output=capture_output,
			text=True,
			timeout=300,  # 5 minute timeout
		)

		# Write logs to file
		with open(log_file, "w") as f:
			f.write(f"Command: {' '.join(args)}\n")
			f.write(f"Exit code: {result.returncode}\n")
			f.write(f"\n=== STDOUT ===\n{result.stdout}\n")
			f.write(f"\n=== STDERR ===\n{result.stderr}\n")

		success = result.returncode == 0
		return success, result.stdout, str(log_file)

	except subprocess.TimeoutExpired:
		with open(log_file, "w") as f:
			f.write(f"Command: {' '.join(args)}\n")
			f.write("Error: Command timed out after 300 seconds\n")
		return False, "", str(log_file)
	except Exception as e:
		with open(log_file, "w") as f:
			f.write(f"Command: {' '.join(args)}\n")
			f.write(f"Error: {str(e)}\n")
		return False, "", str(log_file)


@app.list_tools()
async def list_tools() -> list[Tool]:
	"""List available Nix tools."""
	return [
		Tool(
			name="nix_build",
			description="Build a Nix derivation or flake. Returns success status, optional store path, and log file path.",
			inputSchema={
				"type": "object",
				"properties": {
					"flake_ref": {
						"type": "string",
						"description": "Flake reference (e.g., '.#default', 'nixpkgs#hello', '/path/to/flake#package')",
					},
					"extra_args": {
						"type": "array",
						"items": {"type": "string"},
						"description": "Additional arguments to pass to nix build",
						"default": [],
					},
				},
				"required": ["flake_ref"],
			},
		),
		Tool(
			name="nix_eval",
			description="Evaluate a Nix expression or flake attribute. Returns the evaluation result and log file path.",
			inputSchema={
				"type": "object",
				"properties": {
					"flake_ref": {
						"type": "string",
						"description": "Flake reference or expression (e.g., '.#packages.x86_64-linux.default.version', 'nixpkgs#legacyPackages.x86_64-linux.hello.version')",
					},
					"raw": {
						"type": "boolean",
						"description": "Output raw result without quotes (adds --raw flag)",
						"default": False,
					},
					"json": {
						"type": "boolean",
						"description": "Output result as JSON (adds --json flag)",
						"default": False,
					},
				},
				"required": ["flake_ref"],
			},
		),
		Tool(
			name="nix_flake_show",
			description="Show the outputs of a flake. Returns structured output information and log file path.",
			inputSchema={
				"type": "object",
				"properties": {
					"flake_ref": {
						"type": "string",
						"description": "Flake reference (e.g., '.', 'nixpkgs', 'github:owner/repo')",
						"default": ".",
					},
				},
			},
		),
		Tool(
			name="nix_flake_check",
			description="Check a Nix flake for errors. Returns success status and log file path.",
			inputSchema={
				"type": "object",
				"properties": {
					"flake_ref": {
						"type": "string",
						"description": "Flake reference (e.g., '.', '/path/to/flake', 'github:owner/repo')",
						"default": ".",
					},
				},
			},
		),
		Tool(
			name="nix_search",
			description="Search for Nix packages. Returns search results and log file path.",
			inputSchema={
				"type": "object",
				"properties": {
					"query": {
						"type": "string",
						"description": "Search query (e.g., 'python', 'firefox', '^python3$')",
					},
					"flake_ref": {
						"type": "string",
						"description": "Flake to search in (default: nixpkgs)",
						"default": "nixpkgs",
					},
				},
				"required": ["query"],
			},
		),
	]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
	"""Handle tool calls for Nix operations."""

	if name == "nix_build":
		flake_ref = arguments["flake_ref"]
		extra_args = arguments.get("extra_args", [])

		args = ["nix", "build", flake_ref, "--show-trace", "--print-out-paths"] + extra_args
		success, stdout, log_file = run_nix_command(args, "build")

		result = {
			"success": success,
			"log_file": log_file,
		}

		# If successful, extract store path from output
		if success and stdout.strip():
			# Last line should be the store path
			lines = stdout.strip().split("\n")
			store_path = lines[-1].strip()
			if store_path.startswith("/nix/store/"):
				result["store_path"] = store_path

		return [TextContent(type="text", text=json.dumps(result, indent=2))]

	elif name == "nix_eval":
		flake_ref = arguments["flake_ref"]
		raw = arguments.get("raw", False)
		as_json = arguments.get("json", False)

		args = ["nix", "eval", flake_ref, "--show-trace"]
		if raw:
			args.append("--raw")
		if as_json:
			args.append("--json")

		success, stdout, log_file = run_nix_command(args, "eval")

		result = {
			"success": success,
			"log_file": log_file,
		}

		if success:
			result["result"] = stdout.strip()

		return [TextContent(type="text", text=json.dumps(result, indent=2))]

	elif name == "nix_flake_show":
		flake_ref = arguments.get("flake_ref", ".")

		args = ["nix", "flake", "show", flake_ref, "--json"]
		success, stdout, log_file = run_nix_command(args, "flake-show")

		result = {
			"success": success,
			"log_file": log_file,
		}

		if success:
			try:
				result["outputs"] = json.loads(stdout)
			except json.JSONDecodeError:
				result["outputs"] = stdout.strip()

		return [TextContent(type="text", text=json.dumps(result, indent=2))]

	elif name == "nix_flake_check":
		flake_ref = arguments.get("flake_ref", ".")

		args = ["nix", "flake", "check", flake_ref, "--show-trace"]
		success, stdout, log_file = run_nix_command(args, "flake-check")

		result = {
			"success": success,
			"log_file": log_file,
		}

		return [TextContent(type="text", text=json.dumps(result, indent=2))]

	elif name == "nix_search":
		query = arguments["query"]
		flake_ref = arguments.get("flake_ref", "nixpkgs")

		args = ["nix", "search", flake_ref, query, "--json"]
		success, stdout, log_file = run_nix_command(args, "search")

		result = {
			"success": success,
			"log_file": log_file,
		}

		if success:
			try:
				search_results = json.loads(stdout)
				result["results"] = search_results
				result["count"] = len(search_results)
			except json.JSONDecodeError:
				result["results"] = stdout.strip()

		return [TextContent(type="text", text=json.dumps(result, indent=2))]

	else:
		return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
	"""Run the MCP server."""
	from mcp.server.stdio import stdio_server

	async with stdio_server() as (read_stream, write_stream):
		await app.run(
			read_stream,
			write_stream,
			app.create_initialization_options()
		)


if __name__ == "__main__":
	asyncio.run(main())
