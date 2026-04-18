from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from product_memory_mcp.store import ProductMemoryStore
from product_memory_mcp.tools import ProductMemoryTools, ToolError

PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    def __init__(self, tools: ProductMemoryTools) -> None:
        self.tools = tools
        self.initialized = False

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        params = message.get("params", {})
        request_id = message.get("id")

        if method == "notifications/initialized":
            self.initialized = True
            return None

        if method == "initialize":
            self.initialized = True
            return self._response(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {
                        "name": "product-memory-mcp",
                        "version": "0.1.0",
                    },
                },
            )

        if not self.initialized:
            return self._error(request_id, -32002, "Server not initialized.")

        if method == "tools/list":
            return self._response(request_id, {"tools": self.tools.list_tools()})

        if method == "tools/call":
            try:
                result = self.tools.call_tool(
                    name=params.get("name", ""),
                    arguments=params.get("arguments", {}),
                )
            except ToolError as exc:
                return self._response(
                    request_id,
                    {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                )
            return self._response(request_id, result)

        if method == "resources/list":
            return self._response(request_id, {"resources": self.tools.list_resources()})

        if method == "resources/read":
            try:
                result = self.tools.read_resource(params.get("uri", ""))
            except ToolError as exc:
                return self._error(request_id, -32010, str(exc))
            return self._response(request_id, result)

        return self._error(request_id, -32601, f"Method not found: {method}")

    def _response(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def default_store_path() -> Path:
    configured = os.environ.get("PRODUCT_MEMORY_STORE_PATH")
    if configured:
        return Path(configured)
    return Path.cwd() / ".product_memory" / "store.json"


def build_server() -> MCPServer:
    store = ProductMemoryStore(default_store_path())
    return MCPServer(ProductMemoryTools(store))


def main() -> None:
    server = build_server()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        else:
            response = server.handle_message(message)

        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
