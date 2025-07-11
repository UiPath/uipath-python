import subprocess
import sys
import tempfile
from pathlib import Path

# Simple test
test_code = """
import httpx

def test():
    client = httpx.Client()
    return client
"""

linter_path = Path(__file__).parent / "lint_httpx_client.py"

with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
    f.write(test_code)
    f.flush()

    print(f"Testing file: {f.name}")
    result = subprocess.run(
        [sys.executable, str(linter_path), f.name], capture_output=True, text=True
    )

    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")
