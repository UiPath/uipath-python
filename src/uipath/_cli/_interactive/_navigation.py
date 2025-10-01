"""Navigation and input handling for interactive CLI."""

import sys
import termios
import tty

from .._utils._console import ConsoleLogger

console = ConsoleLogger()


def has_termios() -> bool:
    """Check if we have termios support for advanced input."""
    try:
        termios.tcgetattr(sys.stdin)
        return True
    except Exception:
        return False


HAS_NAVIGATION = has_termios()


class NavigationMixin:
    """Mixin for navigation and input handling."""

    def _clear_screen(self) -> None:
        """Clear the screen."""
        print("\033[2J\033[H", end="")

    def _get_input(self, prompt: str) -> str:
        """Get input from user."""
        return input(prompt).strip()

    def _get_key_input(self) -> str:
        """Get key input with arrow key support."""
        if not HAS_NAVIGATION:
            return input("➤ ").strip().lower()

        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin)

            # Read first character
            char = sys.stdin.read(1)

            # Check for escape sequences (arrow keys)
            if char == '\x1b':  # ESC
                next_char = sys.stdin.read(1)
                if next_char == '[':
                    arrow = sys.stdin.read(1)
                    if arrow == 'A':
                        return 'up'
                    elif arrow == 'B':
                        return 'down'
                return ''

            # Backspace handling
            if char == '\x7f':  # Backspace (DEL)
                return 'back'
            elif char == '\x08':  # Backspace (BS)
                return 'back'

            # Enter key
            if char in ['\r', '\n']:
                return 'enter'

            # Digit keys
            elif char.isdigit() and 1 <= int(char) <= 6:
                return char
            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt

            return ''
        except Exception:
            return input("➤ ").strip().lower()
        finally:
            # Restore terminal settings
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    def _show_ascii_art(self) -> None:
        """Display ASCII art banner."""
        art = """
  ██╗   ██╗██╗██████╗  █████╗ ████████╗██╗  ██╗
  ██║   ██║██║██╔══██╗██╔══██╗╚══██╔══╝██║  ██║
  ██║   ██║██║██████╔╝███████║   ██║   ███████║
  ██║   ██║██║██╔═══╝ ██╔══██║   ██║   ██╔══██║
  ╚██████╔╝██║██║     ██║  ██║   ██║   ██║  ██║
   ╚═════╝ ╚═╝╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝

            Evaluation Builder
        Interactive Evaluation Toolkit
        """
        console.info(art)

    def _show_menu(self, current_selection: int, menu_items: list[str]) -> None:
        """Show menu with current selection highlighted."""
        console.info("\n⚙️  Main Menu:")
        console.info("─" * 65)
        for i, item in enumerate(menu_items):
            if i == current_selection:
                console.info(f"  ▶ {item}")
            else:
                console.info(f"    {item}")
        console.info("\n💡 Use ↑/↓ arrows to navigate, Enter to select, or type 1-6")
        console.info("Press Ctrl+C to exit")
