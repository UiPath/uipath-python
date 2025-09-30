"""Utility functions for error handling and message extraction."""


def extract_clean_error_message(error: Exception, default_message: str = "Execution error") -> str:
    """Extract a clean, user-friendly error message from an exception.

    This function handles common error patterns and formats them for display:
    - Validation errors: Extracts "Input should be..." messages
    - Agent execution errors: Removes prefixes and cleans up format
    - Generic errors: Returns the first line of the error message

    Args:
        error: The exception to extract the message from
        default_message: Fallback message if extraction fails

    Returns:
        A clean, user-friendly error message string
    """
    error_msg = str(error)

    try:
        if "validation error" in error_msg.lower():
            lines = error_msg.split('\n')
            for line in lines:
                if 'Input should be' in line:
                    clean_msg = line.strip()
                    if clean_msg.startswith('  '):
                        clean_msg = clean_msg.strip()
                    return clean_msg
        elif "Agent execution failed:" in error_msg:
            return error_msg.replace("Agent execution failed:", "").strip()
        elif "Error:" in error_msg:
            parts = error_msg.split("Error:")
            if len(parts) > 1:
                return parts[-1].strip()
        else:
            lines = error_msg.split('\n')
            return lines[0] if lines else "Unknown error"
    except Exception:
        pass

    return default_message