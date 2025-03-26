import sys


# Add the wrapper class for LoggerWriter
class FilenoLoggerWriter:
    """Wrapper for LoggerWriter that adds a fileno method."""

    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        # Open the null device once and keep its file descriptor
        import os

        try:
            self._devnull = open(os.devnull, "w")
        except:
            self._devnull = None

    def write(self, data):
        return self.original_stderr.write(data)

    def flush(self):
        if hasattr(self.original_stderr, "flush"):
            return self.original_stderr.flush()

    def fileno(self):
        # Return a valid file descriptor for the null device
        if self._devnull:
            return self._devnull.fileno()
        # Fallback to subprocess.DEVNULL if available
        try:
            from subprocess import DEVNULL

            return DEVNULL
        except:
            return -1  # Last resort fallback


def patch_logger():
    # Patch sys.stderr if it doesn't have fileno
    if not hasattr(sys.stderr, "fileno"):
        sys.stderr = FilenoLoggerWriter(sys.stderr)
