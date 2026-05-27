import sys
import asyncio
from http.client import responses as HTTP_RESPONSES
from urllib.parse import unquote
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import app


def make_scope(environ):
    path = unquote(environ.get("PATH_INFO", ""))
    query_string = environ.get("QUERY_STRING", "").encode("latin-1")
    server = (environ.get("SERVER_NAME"), int(environ.get("SERVER_PORT", "80")))
    client = None
    if environ.get("REMOTE_ADDR"):
        try:
            client = (environ.get("REMOTE_ADDR"), int(environ.get("REMOTE_PORT", "0")))
        except ValueError:
            client = (environ.get("REMOTE_ADDR"), 0)

    headers = []
    for name, value in environ.items():
        if name.startswith("HTTP_"):
            header_name = name[5:].replace("_", "-").lower().encode("latin-1")
            headers.append((header_name, value.encode("latin-1")))
    for header in ("CONTENT_TYPE", "CONTENT_LENGTH"):
        if header in environ:
            header_name = header.replace("_", "-").lower().encode("latin-1")
            headers.append((header_name, environ[header].encode("latin-1")))

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.1"},
        "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/", 1)[-1],
        "method": environ["REQUEST_METHOD"],
        "scheme": environ.get("wsgi.url_scheme", "http"),
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string,
        "headers": headers,
        "client": client,
        "server": server,
    }


def application(environ, start_response):
    body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH", "0") or 0))
    response_status = None
    response_headers = []
    response_body = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        nonlocal response_status, response_headers

        if message["type"] == "http.response.start":
            status_code = message["status"]
            reason = HTTP_RESPONSES.get(status_code, "UNKNOWN")
            response_status = f"{status_code} {reason}"
            response_headers = [
                (name.decode("latin-1"), value.decode("latin-1"))
                for name, value in message.get("headers", [])
            ]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    async def run_app():
        scope = make_scope(environ)
        await app(scope, receive, send)

    asyncio.run(run_app())

    start_response(response_status or "500 Internal Server Error", response_headers)
    return response_body
