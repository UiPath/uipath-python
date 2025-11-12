BINDINGS_VERSION = "2.2"

# Agent.json constants
AGENT_VERSION = "1.0.0"
AGENT_STORAGE_VERSION = "1.0.0"
AGENT_INITIAL_CODE_VERSION = "1.0.0"
AGENT_TARGET_RUNTIME = "python"

# Binary file extension categories
IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".tiff",
    ".webp",
    ".svg",
}

DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls"}

ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz"}

MEDIA_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",
}

FONT_EXTENSIONS = {".woff", ".woff2", ".ttf", ".otf", ".eot"}

EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bin"}

DATABASE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}

PYTHON_BINARY_EXTENSIONS = {".pickle", ".pkl"}

SPECIAL_EXTENSIONS = {""}  # Extensionless binary files

# Pre-compute the union for optimal performance
BINARY_EXTENSIONS = (
    IMAGE_EXTENSIONS
    | DOCUMENT_EXTENSIONS
    | ARCHIVE_EXTENSIONS
    | MEDIA_EXTENSIONS
    | FONT_EXTENSIONS
    | EXECUTABLE_EXTENSIONS
    | DATABASE_EXTENSIONS
    | PYTHON_BINARY_EXTENSIONS
    | SPECIAL_EXTENSIONS
)

EVALS_DIRECTORY_NAME = "evals"


def is_binary_file(file_extension: str) -> bool:
    """Determine if a file should be treated as binary."""
    return file_extension.lower() in BINARY_EXTENSIONS
