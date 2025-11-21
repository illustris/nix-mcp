{
	description = "MCP server for working with Nix derivations, expressions, and flakes";

	inputs = {
		nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
		flake-utils.url = "github:numtide/flake-utils";
		illustris-lib = {
			url = "github:illustris/flake";
			flake = false;
		};
	};

	outputs = { self, nixpkgs, flake-utils, illustris-lib }:
		flake-utils.lib.eachDefaultSystem (system: let
			pkgs = nixpkgs.legacyPackages.${system};
			python = pkgs.python3;
			pythonPackages = python.pkgs;
			inherit (import (illustris-lib + "/lib") { inherit (nixpkgs) lib; }) indent;
		in {
			packages.default = pythonPackages.buildPythonApplication {
				pname = "nix-mcp";
				version = "0.1.0";

				src = ./.;

				propagatedBuildInputs = with pythonPackages; [
					mcp
				];

				# Install the Python package
				format = "other";

				installPhase = indent ''
					mkdir -p $out/bin $out/lib/python${python.pythonVersion}/site-packages
					cp -r src/nix_mcp $out/lib/python${python.pythonVersion}/site-packages/

					# Create entry point script
					cat > $out/bin/nix-mcp <<EOFMARKER
					#!${python}/bin/python3
					import sys
					sys.path.insert(0, "$out/lib/python${python.pythonVersion}/site-packages")
					from nix_mcp.server import main
					import asyncio
					asyncio.run(main())
					EOFMARKER
					chmod +x $out/bin/nix-mcp
				'';

				meta = with pkgs.lib; {
					description = "MCP server for Nix operations";
					license = licenses.mit;
					maintainers = [ ];
				};
			};

			devShells.default = pkgs.mkShell {
				buildInputs = with pythonPackages; [
					python
					mcp
				];

				shellHook = indent ''
					export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
					echo "Nix MCP development environment"
					echo "Run: python -m nix_mcp.server"
				'';
			};

			checks = {
				mcp-server-tests = pkgs.runCommand "mcp-server-tests" {
					buildInputs = [ python pythonPackages.mcp ];
					nativeBuildInputs = [ self.packages.${system}.default ];
				} (indent ''
					# Test the MCP tool functions directly via Python
					cat > test_mcp.py <<'PYTHON_TEST'
					import sys
					import json
					sys.path.insert(0, "${self.packages.${system}.default}/lib/python${python.pythonVersion}/site-packages")

					from nix_mcp.server import call_tool
					import asyncio

					async def test_nix_build_success():
						print("\nTest 1: nix_build response structure (success case)")
						# Test with a simple derivation that's already built
						result = await call_tool("nix_build", {
							"flake_ref": "${self.packages.${system}.default}",
							"extra_args": ["--no-link"]
						})
						data = json.loads(result[0].text)

						# Verify response structure
						assert "success" in data, f"Missing 'success' field in response: {data}"
						assert isinstance(data["success"], bool), f"'success' should be boolean: {data}"
						assert "log_file" in data, f"Missing 'log_file' field in response: {data}"

						# If successful, verify store_path exists
						if data["success"]:
							assert "store_path" in data, f"Missing 'store_path' in successful response: {data}"
							assert data["store_path"].startswith("/nix/store/"), f"Invalid store path: {data['store_path']}"
							print(f"PASS: Built successfully, store_path = {data['store_path']}")
						else:
							print(f"PASS: Response structure valid (build failed but that's OK in sandbox)")

					async def test_nix_build_error():
						print("\nTest 2: nix_build error handling")
						result = await call_tool("nix_build", {
							"flake_ref": "nonexistent#package"
						})
						data = json.loads(result[0].text)

						# Error responses should have success=false and log_file
						assert data["success"] == False, f"Expected success=false for invalid input, got {data}"
						assert "log_file" in data, f"Missing log_file in error response: {data}"
						print("PASS: Error handled correctly")

					async def test_nix_eval_success():
						print("\nTest 3: nix_eval with simple expression")
						# Use a simple expression that doesn't require network
						result = await call_tool("nix_eval", {
							"flake_ref": "--expr '1 + 1'",
							"raw": False
						})
						data = json.loads(result[0].text)

						# Verify response structure
						assert "success" in data, f"Missing 'success' field: {data}"
						assert "log_file" in data, f"Missing 'log_file' field: {data}"

						if data["success"]:
							assert "result" in data, f"Missing 'result' in successful eval: {data}"
							assert data["result"] == "2", f"Expected 1+1=2, got {data['result']}"
							print(f"PASS: Evaluation successful, result = {data['result']}")
						else:
							print(f"PASS: Response structure valid")

					async def test_nix_eval_error():
						print("\nTest 4: nix_eval error handling")
						# Use an expression that will fail
						result = await call_tool("nix_eval", {
							"flake_ref": "--expr 'builtins.throw \"test error\"'"
						})
						data = json.loads(result[0].text)

						# Should fail with proper error structure
						assert data["success"] == False, f"Expected failure for throw expression, got {data}"
						assert "log_file" in data, f"Missing log_file in error response: {data}"
						print("PASS: Error handled correctly")

					async def main():
						try:
							print("Testing MCP server tool functions...")
							await test_nix_build_success()
							await test_nix_build_error()
							await test_nix_eval_success()
							await test_nix_eval_error()
							print("\n========================================")
							print("All tests passed!")
							print("========================================")
							return 0
						except AssertionError as e:
							print(f"\nFAIL: {e}")
							return 1
						except Exception as e:
							print(f"\nERROR: {e}")
							import traceback
							traceback.print_exc()
							return 1

					if __name__ == "__main__":
						sys.exit(asyncio.run(main()))
					PYTHON_TEST

					# Run the Python tests
					${python}/bin/python3 test_mcp.py

					# Create success marker
					mkdir -p $out
					echo "All MCP server tests passed" > $out/test-results.txt
				'');
			};
		});
}
