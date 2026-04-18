from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from product_memory_mcp.server import MCPServer, PROTOCOL_VERSION, build_server


def process_http_request(
    mcp_server: MCPServer,
    method: str,
    path: str,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    if method == "GET" and path == "/health":
        return _json_response(HTTPStatus.OK, {"status": "ok"})
    if method == "GET" and path == "/mcp":
        return _json_response(
            HTTPStatus.OK,
            {
                "name": "product-memory-mcp",
                "transport": "http",
                "protocolVersion": PROTOCOL_VERSION,
                "message": "Send MCP JSON-RPC requests with HTTP POST to /mcp.",
            },
        )
    if method == "POST" and path == "/mcp":
        try:
            message = json.loads((body or b"").decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            return _json_response(
                HTTPStatus.BAD_REQUEST,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                },
            )

        response = mcp_server.handle_message(message)
        if response is None:
            return HTTPStatus.ACCEPTED, {"Content-Length": "0"}, b""
        return _json_response(HTTPStatus.OK, response, mcp_protocol_header=True)

    return _json_response(HTTPStatus.NOT_FOUND, {"error": "Not found"})


class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "product-memory-mcp-http/0.1.0"

    @property
    def mcp_server(self) -> MCPServer:
        return self.server.mcp_server  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        status, headers, body = process_http_request(self.mcp_server, "GET", self.path)
        self._send_response(status, headers, body)

    def do_POST(self) -> None:
        content_length = self.headers.get("Content-Length")
        if not content_length:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing Content-Length"})
            return

        raw_body = self.rfile.read(int(content_length))
        status, headers, body = process_http_request(self.mcp_server, "POST", self.path, raw_body)
        self._send_response(status, headers, body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any], mcp_protocol_header: bool = False) -> None:
        response_status, headers, body = _json_response(status, payload, mcp_protocol_header=mcp_protocol_header)
        self._send_response(response_status, headers, body)

    def _send_response(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)


def _json_response(
    status: HTTPStatus,
    payload: dict[str, Any],
    mcp_protocol_header: bool = False,
) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body)),
    }
    if mcp_protocol_header:
        headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
    return int(status), headers, body


def run_http_server(host: str, port: int) -> None:
    server = build_server()
    httpd = ThreadingHTTPServer((host, port), MCPHTTPRequestHandler)
    httpd.mcp_server = server  # type: ignore[attr-defined]
    httpd.serve_forever()


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    run_http_server(host, port)


if __name__ == "__main__":
    main()
