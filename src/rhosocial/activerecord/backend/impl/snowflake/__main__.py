"""Snowflake backend command-line interface.

Provides SQL execution and database introspection capabilities.
"""

import argparse
import sys


def main():
    """Main CLI entry point for the Snowflake backend."""
    parser = argparse.ArgumentParser(
        description="Execute SQL queries against a Snowflake backend.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="rhosocial-activerecord-snowflake 1.0.0.dev2",
    )

    from .cli import register_commands, get_handler, COMMAND_NAMES

    subparsers = parser.add_subparsers(dest="command")
    register_commands(subparsers)

    args = parser.parse_args()

    if args.command is None:
        print(
            f"Error: Please specify a command: {', '.join(COMMAND_NAMES)}",
            file=sys.stderr,
        )
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)

    handler = get_handler(args.command)
    handler(args)


if __name__ == "__main__":
    main()
