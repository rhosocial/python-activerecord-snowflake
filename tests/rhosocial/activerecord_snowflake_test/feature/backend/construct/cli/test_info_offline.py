# tests/rhosocial/activerecord_snowflake_test/feature/backend/construct/cli/test_info_offline.py
"""Pure-mock unit tests for ``cli.info`` (offline, sync paths only).

``test_info_helpers.py`` already pins the pure helpers; this module covers what
it leaves out: the parser contract, the two untested branches of protocol
support checking, the rich display functions (driven with fake ``rich`` modules
so the optional dependency is never required), and ``handle``'s connected /
disconnected / failed-connection / json-vs-rich routing.  No real backend is
constructed and no network call is made.
"""

import argparse
import io
import json
import sys
import types
from contextlib import contextmanager, redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.impl.snowflake.cli import info as mod
from rhosocial.activerecord.backend.impl.snowflake.cli import output as cli_output

#: ``handle`` imports the backend lazily, so patch it at its source module.
BACKEND_TARGET = "rhosocial.activerecord.backend.impl.snowflake.backend.SnowflakeBackend"


def build_parser():
    """Build a real top-level parser carrying the info subparser."""
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    mod.create_parser(subparsers)
    return top


def parse(*argv):
    """Parse an info invocation."""
    return build_parser().parse_args(["info", *argv])


def fake_backend(version=(8, 1, 2), server_version=(8, 1, 2)):
    """A backend stand-in whose dialect reports a fixed version."""
    backend = MagicMock()
    backend.dialect.version = version
    backend.get_server_version.return_value = server_version
    return backend


@contextmanager
def fake_rich_console():
    """Install minimal ``rich`` modules, yielding the fake ``Console`` class."""
    console_module = types.ModuleType("rich.console")

    class Console:
        instances = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.lines = []
            Console.instances.append(self)

        def print(self, *args, **kwargs):
            self.lines.extend(str(arg) for arg in args)

    console_module.Console = Console
    rich_module = types.ModuleType("rich")
    rich_module.console = console_module
    with patch.dict(sys.modules, {"rich": rich_module, "rich.console": console_module}):
        yield Console


# ================================================================== #
# Parser contract
# ================================================================== #


class TestCreateParser:
    def test_defaults(self):
        args = parse()
        assert args.output == "table"
        assert args.verbose == 0
        assert args.version is None
        assert args.rich_ascii is False
        assert args.use_async is False

    @pytest.mark.parametrize("fmt", cli_output.INFO_OUTPUT_CHOICES)
    def test_output_choices_parse(self, fmt):
        assert parse("-o", fmt).output == fmt

    @pytest.mark.parametrize("fmt", ["csv", "tsv", "yaml"])
    def test_an_unsupported_output_exits_two(self, fmt):
        with pytest.raises(SystemExit) as exc:
            parse("-o", fmt)
        assert exc.value.code == 2

    @pytest.mark.parametrize("flags,expected", [([], 0), (["-v"], 1), (["-vv"], 2), (["-vvv"], 3)])
    def test_verbose_is_a_count(self, flags, expected):
        assert parse(*flags).verbose == expected

    def test_version_is_a_string_flag(self):
        assert parse("--version", "7.32.0").version == "7.32.0"

    def test_connection_arguments_flow_through(self):
        args = parse(
            "--account",
            "acct",
            "--database",
            "ANALYTICS",
            "--schema",
            "PUBLIC",
            "--user",
            "u",
            "--password",
            "p",
        )
        assert (args.account, args.database) == ("acct", "ANALYTICS")
        assert (args.schema, args.user, args.password) == ("PUBLIC", "u", "p")

    def test_rich_ascii_flag(self):
        assert parse("--rich-ascii").rich_ascii is True

    def test_help_lists_the_examples(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["info", "--help"])
        out = capsys.readouterr().out
        assert "Examples:" in out
        assert "-vv" in out


# ================================================================== #
# The remaining branches of protocol support checking
# ================================================================== #


class TestCheckProtocolSupportBranches:
    def test_a_method_with_a_required_parameter_is_reported_false(self):
        class Proto:
            def supports_with_arg(self, level):
                return True

        class Dialect:
            def supports_with_arg(self, level):
                return True

        assert mod.check_protocol_support(Dialect(), Proto) == {"supports_with_arg": False}

    def test_a_method_with_only_optional_parameters_is_called(self):
        class Proto:
            def supports_optional(self, level=1):
                return True

        class Dialect:
            def supports_optional(self, level=1):
                return True

        assert mod.check_protocol_support(Dialect(), Proto) == {"supports_optional": True}

    def test_a_method_that_raises_is_reported_false(self):
        class Proto:
            def supports_broken(self):
                raise RuntimeError("boom")

        class Dialect:
            def supports_broken(self):
                raise RuntimeError("boom")

        assert mod.check_protocol_support(Dialect(), Proto) == {"supports_broken": False}

    def test_a_supported_static_method_is_reported_true(self):
        class Proto:
            @staticmethod
            def supports_static():
                return True

        class Dialect:
            @staticmethod
            def supports_static():
                return True

        assert mod.check_protocol_support(Dialect(), Proto) == {"supports_static": True}


# ================================================================== #
# Rich display helpers -- driven with a MagicMock console
# ================================================================== #


class TestDisplayHelpers:
    @pytest.mark.parametrize("value,marker", [(True, "[OK]"), (False, "[X]")])
    def test_method_details(self, value, marker):
        console = MagicMock()
        mod._display_method_details(console, "supports_window_functions", value)
        text = console.print.call_args.args[0]
        assert marker in text
        assert "window functions" in text

    @pytest.mark.parametrize(
        "stats,marker,bar",
        [
            ({"supported": 2, "total": 2, "percentage": 100}, "[OK]", "#" * 20),
            ({"supported": 1, "total": 2, "percentage": 50}, "[~]", "#" * 10 + "-" * 10),
            ({"supported": 1, "total": 4, "percentage": 25}, "[~]", "#" * 5 + "-" * 15),
            ({"supported": 0, "total": 4, "percentage": 0}, "[X]", "-" * 20),
        ],
    )
    def test_protocol_item_progress_bar(self, stats, marker, bar):
        console = MagicMock()
        mod._display_protocol_item(console, "CTESupport", stats, verbose=0)
        text = console.print.call_args.args[0]
        assert marker in text
        assert bar in text
        assert "CTESupport" in text
        assert f"({stats['supported']}/{stats['total']})" in text

    def test_protocol_item_verbose_lists_methods(self):
        console = MagicMock()
        stats = {
            "supported": 1,
            "total": 2,
            "percentage": 50,
            "methods": {"supports_a": True, "supports_b": False},
        }
        mod._display_protocol_item(console, "P", stats, verbose=2)
        assert console.print.call_count == 3  # summary + two methods

    def test_protocol_item_non_verbose_ignores_methods(self):
        console = MagicMock()
        stats = {"supported": 1, "total": 1, "percentage": 100, "methods": {"supports_a": True}}
        mod._display_protocol_item(console, "P", stats, verbose=0)
        assert console.print.call_count == 1

    def test_protocol_item_shows_the_origin_tag(self):
        console = MagicMock()
        stats = {"supported": 1, "total": 1, "percentage": 100, "origin": "override"}
        mod._display_protocol_item(console, "P", stats, verbose=0)
        text = console.print.call_args.args[0]
        assert "P [dim]\\[override][/dim]" in text

    def test_protocol_group_marks_dialect_specific_groups(self):
        console = MagicMock()
        protocols = {"P": {"supported": 1, "total": 1, "percentage": 100}}
        with patch.object(mod, "_display_protocol_item") as item:
            mod._display_protocol_group(console, "Snowflake-specific", protocols, 0)
        assert "dialect-specific" in console.print.call_args.args[0]
        item.assert_called_once_with(console, "P", protocols["P"], 0)

    def test_protocol_group_of_a_normal_family_has_no_marker(self):
        console = MagicMock()
        with patch.object(mod, "_display_protocol_item"):
            mod._display_protocol_group(console, "JOIN Support", {}, 0)
        assert "dialect-specific" not in console.print.call_args.args[0]

    def test_info_rich_header_and_version(self):
        with fake_rich_console() as Console:
            mod._display_info_rich({"protocols": {}}, 0, "8.1.2", is_connected=True)
        console = Console.instances[-1]
        text = "\n".join(console.lines)
        assert "Snowflake Environment Information" in text
        assert "8.1.2" in text
        assert "from actual connection" in text
        assert "Family Overview" in text

    def test_info_rich_disconnected_version_and_detailed_label(self):
        with fake_rich_console() as Console:
            mod._display_info_rich({"protocols": {}}, 2, "8.0.0", is_connected=False)
        text = "\n".join(Console.instances[-1].lines)
        assert "8.0.0" in text
        assert "no database connection" in text
        assert "Detailed" in text

    def test_info_rich_forces_a_terminal(self):
        with fake_rich_console() as Console:
            mod._display_info_rich({"protocols": {}}, 0, "8.0.0")
        assert Console.instances[-1].kwargs == {"force_terminal": True}

    def test_info_rich_dispatches_every_protocol_group(self):
        protocols = {
            "JOIN Support": {"JoinSupport": {"supported": 1, "total": 1, "percentage": 100}},
        }
        with fake_rich_console():
            with patch.object(mod, "_display_protocol_group") as group:
                mod._display_info_rich({"protocols": protocols}, 0, "8.0.0")
        group.assert_called_once()
        assert group.call_args.args[1:] == ("JOIN Support", protocols["JOIN Support"], 0)

    def test_info_rich_renders_the_suggestion_block(self):
        info = {
            "protocols": {},
            "suggestions": {
                "CTESuggestionSupport": {"supported": True},
                "MergeSuggestionSupport": {"supported": False},
            },
        }
        with fake_rich_console() as Console:
            mod._display_info_rich(info, 0, "8.0.0")
        text = "\n".join(Console.instances[-1].lines)
        assert "Suggestion Support:" in text
        assert "CTESuggestionSupport" in text
        assert "MergeSuggestionSupport" in text


# ================================================================== #
# handle() routing
# ================================================================== #


class TestHandleRouting:
    def _run_json(self, argv=(), backend=None):
        """Drive ``handle`` with rich unavailable and return the parsed JSON."""
        out = io.StringIO()
        with redirect_stdout(out), patch.object(
            mod, "create_provider", return_value=MagicMock()
        ) as provider, patch.object(mod, "RICH_AVAILABLE", False):
            if backend is None:
                mod.handle(parse("-o", "json", *argv))
            else:
                with patch.object(mod, "resolve_connection_config_from_args", return_value="CFG"), patch(
                    BACKEND_TARGET, return_value=backend
                ) as factory:
                    mod.handle(parse("-o", "json", *argv))
                assert factory.call_args.kwargs == {"connection_config": "CFG"}
            assert provider.call_args.kwargs == {"ascii_borders": False}
        return json.loads(out.getvalue())

    def test_default_json_shape(self):
        payload = self._run_json()
        assert payload["database"] == {
            "type": "snowflake",
            "version": "8.0.0",
            "version_tuple": [8, 0, 0],
            "connected": False,
        }
        assert payload["server"] == {
            "version": "8.0.0",
            "variables": {},
            "source": "this backend does not expose server variables",
            "connected": False,
        }
        assert payload["features"] == {}
        assert set(payload["capabilities"]) == set(mod.PROTOCOL_FAMILY_GROUPS)
        assert payload["protocols"] == payload["capabilities"]
        assert payload["suggestions"]
        for group in payload["capabilities"].values():
            for entry in group.values():
                assert entry["origin"] in {"reuse", "override", "proprietary"}

    def test_version_flag_sets_the_simulated_version(self):
        payload = self._run_json(("--version", "7.32.0"))
        assert payload["database"]["version"] == "7.32.0"
        assert payload["database"]["version_tuple"] == [7, 32, 0]

    def test_verbose_two_includes_the_support_methods(self):
        payload = self._run_json(("-vv",))
        group = next(iter(payload["protocols"].values()))
        first = next(iter(group.values()))
        assert "methods" in first

    def test_a_connected_backend_supplies_the_version(self):
        payload = self._run_json(("--account", "acct"), backend=fake_backend())
        assert payload["database"]["connected"] is True
        assert payload["database"]["version"] == "8.1.2"
        assert payload["database"]["version_tuple"] == [8, 1, 2]

    def test_a_backend_without_a_server_version_reports_no_version(self):
        payload = self._run_json(("--account", "acct"), backend=fake_backend(server_version=None))
        assert payload["database"]["connected"] is True
        assert payload["database"]["version"] is None

    def test_a_failed_connection_logs_and_uses_defaults(self, capsys):
        backend = MagicMock()
        backend.connect.side_effect = RuntimeError("no network")
        with patch.object(mod, "logger") as logger, patch.object(
            mod, "resolve_connection_config_from_args", return_value="CFG"
        ), patch(BACKEND_TARGET, return_value=backend), patch.object(
            mod, "create_provider", return_value=MagicMock()
        ), patch.object(mod, "RICH_AVAILABLE", False):
            mod.handle(parse("-o", "json", "--account", "acct", "--version", "7.1.0"))
        assert logger.warning.call_count == 2
        payload = json.loads(capsys.readouterr().out)
        assert payload["database"]["connected"] is False
        assert payload["database"]["version"] == "7.1.0"
        backend.disconnect.assert_not_called()

    def test_the_rich_branch_passes_the_legacy_shape_to_the_renderer(self, capsys):
        with patch.object(mod, "create_provider", return_value=MagicMock()) as provider, patch.object(
            mod, "RICH_AVAILABLE", True
        ), patch.object(mod, "_display_info_rich") as render:
            mod.handle(parse("-vv", "--rich-ascii"))
        provider.assert_called_once_with("table", ascii_borders=True)
        legacy, verbose, version, connected = render.call_args.args
        assert set(legacy) == {"snowflake", "protocols", "suggestions"}
        assert legacy["snowflake"]["type"] == "snowflake"
        assert verbose == 2
        assert version == "8.0.0"
        assert connected is False
        assert capsys.readouterr().out == ""

    def test_json_output_does_not_use_the_rich_renderer(self, capsys):
        with patch.object(mod, "create_provider", return_value=MagicMock()), patch.object(
            mod, "RICH_AVAILABLE", True
        ), patch.object(mod, "_display_info_rich") as render:
            mod.handle(parse("-o", "json"))
        render.assert_not_called()
        assert json.loads(capsys.readouterr().out)["database"]["type"] == "snowflake"
