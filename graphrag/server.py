"""HTTP server exposing chat + streaming chat endpoints."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .chat import ChatService


class ChatHandler(BaseHTTPRequestHandler):
    chat_service = ChatService()

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/chat", "/chat/stream"}:
            self._write_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        payload = self._read_json()
        message = payload.get("message", "")

        if self.path == "/chat":
            reply = self.chat_service.generate_reply(message)
            self._write_json({"response": reply})
            return

        # SSE streaming endpoint: /chat/stream
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        for chunk in self.chat_service.stream_reply(message):
            event = f"data: {json.dumps({'delta': chunk})}\n\n".encode("utf-8")
            self.wfile.write(event)
            self.wfile.flush()

        done_event = b"data: {\"done\": true}\n\n"
        self.wfile.write(done_event)
        self.wfile.flush()


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), ChatHandler)
    print(f"Serving chat endpoints on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
