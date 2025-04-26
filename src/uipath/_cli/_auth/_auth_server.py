import http.server
import json
import os
import socketserver
import ssl
import time

import click
from dotenv import load_dotenv

from ._oidc_utils import get_auth_config

load_dotenv()

# Server port
PORT = 6234


# Custom exception for token received
class TokenReceivedSignal(Exception):
    """Exception raised when a token is successfully received."""

    def __init__(self, token_data):
        self.token_data = token_data
        super().__init__("Token received successfully")


def make_request_handler_class(state, code_verifier, token_callback, domain):
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

                # Get the redirect URI from auth config
                auth_config = get_auth_config()
                redirect_uri = auth_config["redirect_uri"]

                content = content.replace("__PY_REPLACE_EXPECTED_STATE__", state)
                content = content.replace("__PY_REPLACE_CODE_VERIFIER__", code_verifier)
                content = content.replace("__PY_REPLACE_REDIRECT_URI__", redirect_uri)
                content = content.replace(
                    "__PY_REPLACE_CLIENT_ID__", auth_config["client_id"]
                )
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


class HTTPSServer:
    def __init__(self, port=6234, cert_file="localhost.crt", key_file="localhost.key"):
        """Initialize HTTPS server with configurable parameters.

        Args:
            port (int, optional): Port number to run the server on. Defaults to 6234.
            cert_file (str, optional): SSL certificate file. Defaults to "localhost.crt".
            key_file (str, optional): SSL key file. Defaults to "localhost.key".
        """
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.port = port
        self.cert_file = os.path.join(self.current_path, "localhost.crt")
        self.key_file = os.path.join(self.current_path, "localhost.key")
        self.httpd = None
        self.token_data = None
        self.should_shutdown = False

    def token_received_callback(self, token_data):
        """Callback for when a token is received.

        Args:
            token_data (dict): The received token data.
        """
        self.token_data = token_data
        self.should_shutdown = True

    def create_server(self, state, code_verifier, domain):
        """Create and configure the HTTPS server.

        Args:
            state (str): The OAuth state parameter.
            code_verifier (str): The PKCE code verifier.
            domain (str): The domain for authentication.

        Returns:
            socketserver.TCPServer: The configured HTTPS server.
        """
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_file, self.key_file)

        # Create server with address reuse
        socketserver.TCPServer.allow_reuse_address = True
        handler = make_request_handler_class(
            state, code_verifier, self.token_received_callback, domain
        )
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)

        return self.httpd

    def start(self, state, code_verifier, domain):
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

        try:
            if self.httpd:
                while not self.should_shutdown:
                    self.httpd.handle_request()
        except KeyboardInterrupt:
            click.echo("Process interrupted by user")
        finally:
            self.stop()

        return self.token_data if self.token_data else {}

    def stop(self):
        """Stop the server gracefully and cleanup resources."""
        if self.httpd:
            self.httpd.server_close()
            self.httpd = None
