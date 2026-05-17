# src/rhosocial/activerecord/backend/impl/snowflake/cli/__init__.py
"""Snowflake CLI common definitions and subcommand registration."""

import importlib

COMMAND_NAMES = [
    'info', 'query', 'introspect',
]


def register_commands(subparsers):
    """Register all subcommands."""
    from .info import create_parser as info_parser
    from .introspect import create_parser as introspect_parser
    info_parser(subparsers)
    introspect_parser(subparsers)


def get_handler(command_name: str):
    """Get the handler function for a subcommand."""
    module_name = command_name.replace('-', '_')
    module = importlib.import_module(f'.{module_name}', __name__)
    return module.handle
