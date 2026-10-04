"""A bounded loopback-only browser transport for the local binding workbench."""

from __future__ import annotations

import argparse
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import catalog, current_language, language_context, msg, tr
from paperdelta.storage import parse_json
from paperdelta.studio import StudioSession, browser_value
from paperdelta.studio_ui import PAGE

MAX_BODY = 1024 * 1024
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'; object-src 'none'"
)


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 16

    def __init__(self, project, config_path="paperdelta.yaml", port=0, language="en"):
        self.session = StudioSession(project, config_path)
        self.language = language
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(16)
        self.assets = {
            "/": ("text/html; charset=utf-8", PAGE.replace("{{LANG}}", language).encode()),
            **{
                "/" + name: (
                    mime,
                    files("paperdelta").joinpath("assets", name).read_bytes(),
                )
                for name, mime in (
                    ("studio.js", "text/javascript; charset=utf-8"),
                    ("studio-review.js", "text/javascript; charset=utf-8"),
                    ("studio-batch.js", "text/javascript; charset=utf-8"),
                    ("studio.css", "text/css; charset=utf-8"),
                )
            },
            "/strings.json": (
                "application/json; charset=utf-8",
                json.dumps(
                    {
                        language: {
                            key.removeprefix("studio."): value
                            for key, value in catalog(language).items()
                            if key.startswith("studio.")
                        }
                        for language in ("en", "zh-CN")
                    },
                    ensure_ascii=False,
                ).encode(),
            ),
        }
        super().__init__(("127.0.0.1", port), StudioHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"

    @property
    def url(self):
        return self.origin + "/#" + self.token

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class StudioHandler(BaseHTTPRequestHandler):
    server_version = "PaperDelta"
    sys_version = ""

    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *args):
        # No project text, bearer token or browser paths in access logs.
        pass

    def _send(self, status, body, mime="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (OSError, TimeoutError):
            pass

    def _json(self, status, body):
        self._send(status, json.dumps(browser_value(body), ensure_ascii=False).encode("utf-8"))

    def _error(self, status, code, key, language=None):
        self._json(
            status,
            {
                "error": code,
                "message": msg("studio." + key).render(language or self.server.language),
            },
        )

    def _boundary(self):
        if (
            self.client_address[0] != "127.0.0.1"
            or self.headers.get_all("Host", []) != [self.server.host]
            or self.headers.get("Sec-Fetch-Site") == "cross-site"
            or (
                self.headers.get_all("Origin", [])
                and self.headers.get_all("Origin") != [self.server.origin]
            )
        ):
            self._error(403, "STUDIO_ORIGIN", "request_denied")
            return False
        return True

    def do_GET(self):
        if not self._boundary():
            return
        asset = self.server.assets.get(self.path)
        if asset is None:
            self._error(404, "STUDIO_NOT_FOUND", "not_found")
        else:
            self._send(200, asset[1], asset[0])

    def do_POST(self):
        lengths = self.headers.get_all("Content-Length", [])
        if (
            len(lengths) != 1
            or not lengths[0].isascii()
            or not lengths[0].isdigit()
            or len(lengths[0]) > 9
            or not 0 < int(lengths[0]) <= MAX_BODY
        ):
            self._error(400, "STUDIO_BODY", "invalid_request")
            return
        language = self.server.language
        try:
            # Consume a bounded, length-framed body before closing a rejected
            # request. Otherwise a later body packet can reset the socket on
            # Windows before the client receives our diagnostic. Parsing and
            # all project access still require the origin and bearer checks.
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                self._error(400, "STUDIO_BODY", "invalid_request")
                return
            if not self._boundary():
                return
            if self.path != "/api":
                self._error(404, "STUDIO_NOT_FOUND", "not_found")
                return
            auth = self.headers.get_all("Authorization", [])
            if (
                len(auth) != 1
                or not auth[0].isascii()
                or not secrets.compare_digest(auth[0], "Bearer " + self.server.token)
                or self.headers.get_all("Origin", []) != [self.server.origin]
            ):
                self._error(403, "STUDIO_SESSION", "session_expired")
                return
            if self.headers.get("Transfer-Encoding") is not None or self.headers.get_all(
                "Content-Type", []
            ) != ["application/json"]:
                self._error(400, "STUDIO_BODY", "invalid_request")
                return
            value = parse_json(raw.decode("utf-8"))
            if isinstance(value, dict) and value.get("language") in {"en", "zh-CN"}:
                language = value["language"]
            with self.server.lock, language_context(language):
                result = self.server.session.execute(value)
            self._json(200, result)
        except PaperDeltaError as exc:
            status = 409 if exc.code.startswith(("STALE_", "STUDIO_REVISION")) else 400
            self._json(status, {"error": exc.code, "message": exc.render(language)})
        except (UnicodeError, ValueError, TypeError, TimeoutError):
            self._error(400, "STUDIO_BODY", "invalid_request", language)
        except OSError:
            self._error(500, "STUDIO_IO", "io_error", language)
        except Exception:
            self._error(500, "STUDIO_INTERNAL", "internal_error", language)

    def do_OPTIONS(self):
        self._error(405, "STUDIO_METHOD", "request_denied")


def _port(value):
    try:
        port = int(value)
        if 0 <= port <= 65535:
            return port
    except ValueError:
        pass
    raise argparse.ArgumentTypeError(tr("studio.port_invalid"))


def register_commands(commands):
    command = commands.add_parser("studio", help=tr("studio.cli_help"))
    command.add_argument("--port", type=_port, default=0, help=tr("studio.port_help"))
    command.add_argument("--no-open", action="store_true", help=tr("studio.no_open_help"))


def run_command(project, arguments):
    with StudioServer(project, arguments.config, arguments.port, current_language()) as server:
        print(tr("studio.listening", url=server.url), flush=True)
        print(tr("studio.stop_hint"), flush=True)
        if not arguments.no_open:
            try:
                webbrowser.open(server.url)
            except webbrowser.Error:
                print(tr("studio.open_failed"), flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0
