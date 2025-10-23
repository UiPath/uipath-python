import asyncio
import http.server
import json
import os
import socketserver
import threading
import time
from typing import Optional

# Server port
PORT = 6234


# Custom exception for token received
class TokenReceivedSignal(Exception):
    """Exception raised when a token is successfully received."""

    def __init__(self, token_data):
        self.token_data = token_data
        super().__init__("Token received successfully")


def make_request_handler_class(
    state, code_verifier, token_callback, domain, redirect_uri, client_id
):
    class SimpleHTTPSRequestHandler(http.server.SimpleHTTPRequestHandler):
        """Simple HTTPS request handler that serves static files."""

        def log_message(self, format, *args) -> None:
            # do nothing
            pass

        def do_POST(self):
            """Handle POST requests to /set_token."""
            if self.path == "/set_token":
                content_length = int(self.headers["Content-Length"])
                post_data = self.rfile.read(content_length)
                token_data = json.loads(post_data.decode("utf-8"))

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Token received")

                time.sleep(1)

                token_callback(token_data)
            elif self.path == "/log":
                content_length = int(self.headers["Content-Length"])
                post_data = self.rfile.read(content_length)
                logs = json.loads(post_data.decode("utf-8"))
                # Write logs to .uipath/.error_log file
                uipath_dir = os.path.join(os.getcwd(), ".uipath")
                os.makedirs(uipath_dir, exist_ok=True)
                error_log_path = os.path.join(uipath_dir, ".error_log")

                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"\n--- Authentication Error Log {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                    )
                    json.dump(logs, f, indent=2)
                    f.write("\n")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Log received")
            else:
                self.send_error(404, "Path not found")

        def do_GET(self):
            """Handle GET requests by serving index.html."""
            # Always serve index.html regardless of the path
            try:
                index_path = os.path.join(os.path.dirname(__file__), "index.html")
                with open(index_path, "r") as f:
                    content = f.read()

                content = content.replace("__PY_REPLACE_EXPECTED_STATE__", state)
                content = content.replace("__PY_REPLACE_CODE_VERIFIER__", code_verifier)
                content = content.replace("__PY_REPLACE_REDIRECT_URI__", redirect_uri)
                content = content.replace("__PY_REPLACE_CLIENT_ID__", client_id)
                content = content.replace("__PY_REPLACE_DOMAIN__", domain)

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            except FileNotFoundError:
                self.send_error(404, "File not found")

        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

    return SimpleHTTPSRequestHandler


class HTTPServer:
    def __init__(self, port=6234, redirect_uri=None, client_id=None):
        """Initialize HTTP server with configurable parameters.

        Args:
            port (int, optional): Port number to run the server on. Defaults to 6234.
            redirect_uri (str, optional): OAuth redirect URI. Defaults to None.
            client_id (str, optional): OAuth client ID. Defaults to None.
        """
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.port = port
        self.redirect_uri = redirect_uri
        self.client_id = client_id
        self.httpd: Optional[socketserver.TCPServer] = None
        self.token_data = None
        self.should_shutdown = False
        self.token_received_event: Optional[asyncio.Event] = None
        self.loop = None

    def token_received_callback(self, token_data):
        """Callback for when a token is received.

        Args:
            token_data (dict): The received token data.
        """
        self.token_data = token_data
        if self.token_received_event and self.loop:
            self.loop.call_soon_threadsafe(self.token_received_event.set)

    def create_server(self, state, code_verifier, domain):
        """Create and configure the HTTP server.

        Args:
            state (str): The OAuth state parameter.
            code_verifier (str): The PKCE code verifier.
            domain (str): The domain for authentication.

        Returns:
            socketserver.TCPServer: The configured HTTP server.
        """
        # Create server with address reuse
        socketserver.TCPServer.allow_reuse_address = True
        handler = make_request_handler_class(
            state,
            code_verifier,
            self.token_received_callback,
            domain,
            self.redirect_uri,
            self.client_id,
        )
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        return self.httpd

    def _run_server(self):
        """Run server loop in thread."""
        try:
            while not self.should_shutdown and self.httpd:
                self.httpd.handle_request()
        except Exception:
            # Server might be closed, that's fine
            pass

    async def start(self, state, code_verifier, domain):
        """Start the server.

        Args:
            state (str): The OAuth state parameter.
            code_verifier (str): The PKCE code verifier.
            domain (str): The domain for authentication.

        Returns:
            dict: The received token data or an empty dict if no token was received.
        """
        if not self.httpd:
            self.create_server(state, code_verifier, domain)

        self.token_received_event = asyncio.Event()
        self.loop = asyncio.get_event_loop()

        # Run server in daemon thread
        server_thread = threading.Thread(target=self._run_server, daemon=True)
        server_thread.start()

        try:
            # Wait indefinitely for token received event or interrupt
            await self.token_received_event.wait()
        finally:
            self.stop()

        return self.token_data if self.token_data else {}

    def stop(self):
        """Stop the server gracefully and cleanup resources."""
        self.should_shutdown = True
        if self.httpd:
            self.httpd.server_close()
            self.httpd = None
