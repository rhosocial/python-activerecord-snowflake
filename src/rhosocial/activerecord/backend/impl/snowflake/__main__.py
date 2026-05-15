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
        version="rhosocial-activerecord-snowflake 1.0.0.dev1",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["info", "query", "introspect"],
        help="Available commands: info, query, introspect",
    )

    args = parser.parse_args()

    if args.command is None:
        print(
            "Error: Please specify a command: 'info', 'query', or 'introspect'",
            file=sys.stderr,
        )
        print("Use --help for more information.", file=sys.stderr)
        sys.exit(1)

    print(f"Command '{args.command}' is not yet implemented.")


if __name__ == "__main__":
    main()
