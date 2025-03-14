import http.server
import json
import os
import socketserver
import ssl
import time

from dotenv import load_dotenv

load_dotenv()

# Server port
PORT = 6234


# Custom exception for token received
class TokenReceivedSignal(Exception):
    """Exception raised when a token is successfully received."""

    def __init__(self, token_data):
        self.token_data = token_data
        super().__init__("Token received successfully")


def make_request_handler_class(state, code_verifier, token_callback):
    class SimpleHTTPSRequestHandler(http.server.SimpleHTTPRequestHandler):
        """Simple HTTPS request handler that serves static files."""

        def log_message(self, format, *args) -> None:
            # do nothing
            pass

        def do_POST(self):
            """Handle POST requests to /set_token"""
            if self.path == "/set_token":
                content_length = int(self.headers["Content-Length"])
                post_data = self.rfile.read(content_length)
                token_data = json.loads(post_data.decode("utf-8"))
                print("Received authentication information")

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Token received")

                time.sleep(1)

                token_callback(token_data)

            else:
                self.send_error(404, "Path not found")

        def do_GET(self):
            """Handle GET requests by serving index.html"""
            # Always serve index.html regardless of the path
            try:
                index_path = os.path.join(os.path.dirname(__file__), "index.html")
                with open(index_path, "r") as f:
                    content = f.read()

                content = content.replace("__PY_REPLACE_EXPECTED_STATE__", state)
                content = content.replace("__PY_REPLACE_CODE_VERIFIER__", code_verifier)

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


class HTTPSServer:
    def __init__(self, port=6234, cert_file="localhost.crt", key_file="localhost.key"):
        """Initialize HTTPS server with configurable parameters."""
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.port = port
        self.cert_file = os.path.join(self.current_path, "localhost.crt")
        self.key_file = os.path.join(self.current_path, "localhost.key")
        self.httpd = None
        self.token_data = None
        self.should_shutdown = False

    def token_received_callback(self, token_data):
        """Callback for when a token is received."""
        self.token_data = token_data
        self.should_shutdown = True

    def create_server(self, state, code_verifier):
        """Create and configure the HTTPS server."""
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_file, self.key_file)

        # Create server
        handler = make_request_handler_class(
            state, code_verifier, self.token_received_callback
        )
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)

        return self.httpd

    def start(self, state, code_verifier):
        """Start the server."""
        if not self.httpd:
            self.create_server(state, code_verifier)

        try:
            if self.httpd:
                while not self.should_shutdown:
                    self.httpd.handle_request()
        except KeyboardInterrupt:
            print("Process interrupted by user")
        finally:
            self.stop()

        return self.token_data if self.token_data else {}

    def stop(self):
        """Stop the server gracefully."""
        if self.httpd:
            self.httpd.server_close()
            self.httpd = None
