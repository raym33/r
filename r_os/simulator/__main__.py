"""
R OS Simulator - CLI Entry Point.

Run with: python -m r_os.simulator
Or: r-os (after pip install)
"""

import argparse
import sys


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="R OS - Android Simulator for Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  r-os                    # Launch simulator with default theme
  r-os --theme amoled     # Launch with AMOLED theme
  r-os --theme light      # Launch with light theme

Keyboard shortcuts:
  t     - Cycle themes
  n     - Toggle notifications
  h     - Go home
  Esc   - Go back
  q     - Quit
        """,
    )

    parser.add_argument(
        "--theme",
        "-t",
        choices=["material", "amoled", "light"],
        default="material",
        help="Color theme (default: material)",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="R OS Simulator 1.0.0",
    )

    args = parser.parse_args()

    try:
        from r_os.simulator.app import run_simulator

        run_simulator(theme=args.theme)
        return 0

    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Install with: pip install textual")
        return 1

    except KeyboardInterrupt:
        print("\nBye!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
