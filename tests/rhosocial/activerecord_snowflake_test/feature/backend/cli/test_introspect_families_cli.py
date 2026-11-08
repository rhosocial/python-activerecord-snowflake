# tests/rhosocial/activerecord_snowflake_test/feature/backend/cli/test_introspect_families_cli.py
"""The nine families the dialect answers, as the CLI asks for them.

No server is needed here. What is checked is the wiring the CLI owns: that
each type reaches its introspector method, that NAME and the type-specific
flags arrive as arguments rather than being parsed and dropped, and that a
family the connected server refuses is refused. Whether the answer is right is
the introspector's question, and the live tests carry it.

The stub introspector records one call per run, so a branch that calls two
methods, or calls the right one with a dropped argument, fails here rather
than showing up as a plausible-looking listing.

Six of the nine are families this dialect cannot answer -- the switch is
inherited as ``False`` -- so the gate is what the run meets, and the tests
hold both sides of it: the refusal before anything connects, and the branch
that does run once a stub dialect answers ``True``. Six families answering
``False`` is the honest state of this backend, and a CLI that runs them anyway
would render a statement on a catalogue Snowflake does not have.

Every type is driven through the real parser rather than a hand-built
namespace, so a flag the subparser does not declare fails here rather than
reading as an argument the branch silently ignored.
"""

import argparse
import json
from typing import List, Optional

import pytest

from rhosocial.activerecord.backend.impl.snowflake.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.introspection.types import (
    ColumnDataProfile,
    ColumnValueFrequency,
    DDLStatement,
    JoinCoverage,
)

#: The nine families this change wires, and the switch that gates each. The
#: dialect declares the three data families and inherits the other six as
#: ``False``, so the three are asked and the six are refused -- both of which
#: the CLI must be able to do.
NEW_FAMILIES = {
    "unused-indexes": "supports_unused_indexes_detection",
    "table-stats": "supports_table_stats",
    "runtime": "supports_runtime_stats",
    "index-stats": "supports_index_stats",
    "dependencies": "supports_object_dependencies",
    "ddl": "supports_ddl_extraction",
    "column-profiles": "supports_column_data_profile",
    "value-samples": "supports_column_value_sample",
    "join-coverage": "supports_join_coverage",
}

#: The families that answer for the whole connection's scope and take no NAME.
WHOLE_SCOPE_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
)

#: The families this dialect cannot answer, so the gate refuses them. The
#: remaining three read the rows themselves and are the ones whose branch
#: runs against a real dialect.
GATED_FAMILIES = (
    "unused-indexes",
    "table-stats",
    "runtime",
    "index-stats",
    "dependencies",
    "ddl",
)

#: The families a real dialect answers, so their branch is reachable live.
ANSWERED_FAMILIES = (
    "column-profiles",
    "value-samples",
    "join-coverage",
)

#: Connection arguments every argv needs: Snowflake asks for an account and/or
#: a database, and neither is a capability answer.
CONNECTION = ["--account", "acct"]


class _RecordingIntrospector:
    """Records each introspection call, and returns what the test declared.

    ``__getattr__`` is the whole implementation: a test names the method once,
    in the assertion, and a branch that reaches a different one fails on the
    recorded name rather than on an attribute error that would hide the typo.
    """

    def __init__(self, results: Optional[dict] = None) -> None:
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    """The async shape of the same recorder: methods are awaited, calls are not."""

    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AllTrueDialect:
    """Every capability switch answers True, so the gate never refuses.

    A run against a real server answers the switch from the live dialect;
    offline, the gate is exercised directly with a dialect of its own.
    """

    def __getattr__(self, name: str):
        if name.startswith("supports_"):
            return lambda: True
        raise AttributeError(name)


class _RecordingProvider:
    """An output provider that records instead of printing."""

    def __init__(self) -> None:
        self.results: List[object] = []

    def display_results(self, data, title=None):
        self.results.append((title, data))

    def display_connection_error(self, error):
        pass

    def display_query_error(self, error):
        pass


def build_parser():
    """Build the top-level parser with the real introspect subparser."""
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    introspect_cli.create_parser(subparsers)
    return top


def _patch_backend(monkeypatch, introspector, dialect=None, use_async=False):
    """Install a stub backend class whose instances carry *introspector*.

    The class name written into the module is the one ``handle()`` looks up,
    so the sync and the async chains are each installed separately. A
    *dialect* other than the answer-everything stub is what the gate tests
    need -- a real ``SnowflakeDialect`` answers the six switches ``False``,
    which is the refusal path.
    """
    target = (
        introspect_cli.AsyncSnowflakeBackend.__name__
        if use_async
        else introspect_cli.SnowflakeBackend.__name__
    )
    chosen = _AllTrueDialect if dialect is None else dialect

    class _Backend:
        def __init__(self, connection_config=None):
            self.connection_config = connection_config
            self.introspector = introspector
            self.dialect = chosen()
            self._connection = object()
            self.disconnected = False

    if use_async:
        async def connect(self):
            pass

        async def disconnect(self):
            self.disconnected = True

        _Backend.connect = connect
        _Backend.disconnect = disconnect
    else:
        def connect(self):
            pass

        def disconnect(self):
            self.disconnected = True

        _Backend.connect = connect
        _Backend.disconnect = disconnect

    monkeypatch.setattr(introspect_cli, target, _Backend)
    monkeypatch.setattr(
        introspect_cli, "resolve_connection_config_from_args", lambda _args: None
    )
    return _Backend


def _run_sync(monkeypatch, introspector, argv, dialect=None):
    """Drive a full run through the real parser and dispatch chain."""
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect)
    introspect_cli.handle(build_parser().parse_args(argv))


def _run_async(monkeypatch, introspector, argv, dialect=None):
    """Drive the async chain the same way, through the same parser."""
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect, use_async=True)
    introspect_cli.handle(build_parser().parse_args(argv + ["--use-async"]))


def _run_with_real_provider(monkeypatch, introspector, argv):
    """A run that keeps the real providers, so stdout is the serialised rows."""
    _patch_backend(monkeypatch, introspector)
    introspect_cli.handle(build_parser().parse_args(argv))


def _name_required_argv(type_, extra=()):
    return ["introspect", type_, "orders"] + list(extra) + CONNECTION


class TestTheSchemaWideFamilies:
    """The counters and listings describe the connection, so NAME is refused."""

    @pytest.mark.parametrize(
        "type_, method",
        [
            ("unused-indexes", "list_unused_indexes"),
            ("table-stats", "list_table_usage_stats"),
            ("runtime", "list_runtime_metrics"),
            ("index-stats", "list_index_usage_stats"),
        ],
    )
    def test_the_family_asks_its_method_for_the_whole_scope(
        self, type_, method, monkeypatch
    ):
        introspector = _RecordingIntrospector({method: []})

        _run_sync(monkeypatch, introspector, ["introspect", type_] + CONNECTION)

        assert introspector.calls == [(method, (), {"schema": None})]

    @pytest.mark.parametrize("type_", WHOLE_SCOPE_FAMILIES)
    def test_a_name_is_refused(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._refuse_name(
                build_parser().parse_args(["introspect", type_, "orders"] + CONNECTION)
            )
        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", WHOLE_SCOPE_FAMILIES)
    def test_the_refusal_happens_before_anything_connects(self, type_, monkeypatch):
        """The refusal is a statement about the command line, not the server."""
        introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit):
            _run_sync(
                monkeypatch,
                introspector,
                ["introspect", type_, "orders"] + CONNECTION,
            )

        assert introspector.calls == []


class TestTheDependenciesBranch:
    """One optional NAME narrows the graph; omitting it asks for all of it."""

    def test_a_named_object_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(
            monkeypatch, introspector, ["introspect", "dependencies", "posts"] + CONNECTION
        )

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": "posts", "schema": None})
        ]

    def test_an_unnamed_run_asks_for_the_whole_graph(self, monkeypatch):
        introspector = _RecordingIntrospector({"list_object_dependencies": []})

        _run_sync(monkeypatch, introspector, ["introspect", "dependencies"] + CONNECTION)

        assert introspector.calls == [
            ("list_object_dependencies", (), {"object_name": None, "schema": None})
        ]


class TestTheDdlBranch:
    """The schema object, not a name, is what a caller parses."""

    def _statement(self) -> DDLStatement:
        return DDLStatement(
            schema=None,
            object_type="TABLE",
            object_name="orders",
            ddl="CREATE TABLE ORDERS (ID NUMBER)",
            native=True,
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector({"get_ddl_statement": self._statement()})

        _run_sync(monkeypatch, introspector, _name_required_argv("ddl"))

        assert introspector.calls == [
            ("get_ddl_statement", ("orders",), {"object_type": None, "schema": None})
        ]

    def test_the_engine_text_reaches_json_with_its_native_flag(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector({"get_ddl_statement": self._statement()})

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("ddl", ["-o", "json"])
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["object_name"] == "orders"
        assert payload[0]["ddl"] == "CREATE TABLE ORDERS (ID NUMBER)"
        assert payload[0]["native"] is True

    def test_no_ddl_is_an_error_not_an_empty_listing(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector({"get_ddl_statement": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, introspector, _name_required_argv("ddl"))

        assert excinfo.value.code == 1
        assert "no DDL available" in capsys.readouterr().err


class TestTheColumnProfilesBranch:
    """The aggregate label must reach the reader; the numbers are not a catalogue."""

    def _profile(self) -> ColumnDataProfile:
        return ColumnDataProfile(
            schema=None,
            table_name="orders",
            column_name="status",
            null_fraction=0.6,
            distinct_count=3,
            row_count=100,
            source="aggregate",
        )

    def test_the_table_is_asked_for_by_name(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _name_required_argv("column-profiles"))

        assert introspector.calls == [
            ("list_column_data_profiles", ("orders",), {"schema": None})
        ]

    def test_the_run_says_the_numbers_are_aggregated(self, monkeypatch, capsys):
        """Exact and expensive, on stderr so the JSON on stdout stays parseable."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_sync(monkeypatch, introspector, _name_required_argv("column-profiles"))

        captured = capsys.readouterr()
        assert "aggregate" in captured.err
        assert "full scan" in captured.err

    def test_the_note_is_not_mistaken_for_a_result_row(self, monkeypatch, capsys):
        """The note belongs on stderr; a line on stdout would break every parser."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("column-profiles", ["-o", "json"])
        )

        out = capsys.readouterr().out
        assert out.lstrip().startswith("[")
        json.loads(out)

    def test_the_source_rides_the_row_rather_than_a_note(self, monkeypatch, capsys):
        """``source`` is a column of the answer, so a machine reader sees it."""
        introspector = _RecordingIntrospector(
            {"list_column_data_profiles": [self._profile()]}
        )

        _run_with_real_provider(
            monkeypatch, introspector, _name_required_argv("column-profiles", ["-o", "json"])
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["source"] == "aggregate"


class TestTheValueSamplesBranch:
    """A table and a column, and a limit that the introspector receives."""

    def test_the_table_column_and_limit_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value="PAID", count=7)]}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "status", "--limit", "20"]),
        )

        assert introspector.calls == [
            (
                "sample_column_values",
                ("orders", "status"),
                {"limit": 20, "schema": None},
            )
        ]

    def test_no_limit_is_sent_when_the_flag_is_omitted(self, monkeypatch):
        introspector = _RecordingIntrospector({"sample_column_values": []})

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "status"]),
        )

        # Absent ``--limit`` means absent from the call: the introspector's own
        # signature answers with its own default, and the CLI does not restate
        # it. A number here would fail the day the signature's default moved.
        assert "limit" not in introspector.calls[0][2]

    def test_the_value_null_is_not_silently_dropped(self, monkeypatch, capsys):
        """A NULL is a legal member of a value domain, often the most interesting."""
        import json

        introspector = _RecordingIntrospector(
            {"sample_column_values": [ColumnValueFrequency(value=None, count=5)]}
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            _name_required_argv("value-samples", ["--column", "status", "-o", "json"]),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["value"] is None
        assert payload[0]["count"] == 5


class TestTheJoinCoverageBranch:
    """Four names, both sides of the measurement, in the order they are asked."""

    def _coverage(self) -> JoinCoverage:
        return JoinCoverage(
            left_schema=None,
            left_table="orders",
            left_column="BUYER_ID",
            right_schema=None,
            right_table="users",
            right_column="ID",
            left_coverage=1.0,
            right_coverage=0.75,
        )

    _right_flags = ["--right-table", "users", "--right-column", "ID"]

    def test_the_four_names_reach_the_introspector(self, monkeypatch):
        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_sync(
            monkeypatch,
            introspector,
            _name_required_argv("join-coverage", ["--column", "BUYER_ID"] + self._right_flags),
        )

        assert introspector.calls == [
            (
                "estimate_join_coverage",
                ("orders", "BUYER_ID", "users", "ID"),
                {"schema": None},
            )
        ]

    def test_both_fractions_are_reported(self, monkeypatch, capsys):
        import json

        introspector = _RecordingIntrospector(
            {"estimate_join_coverage": self._coverage()}
        )

        _run_with_real_provider(
            monkeypatch,
            introspector,
            _name_required_argv(
                "join-coverage", ["--column", "BUYER_ID"] + self._right_flags + ["-o", "json"]
            ),
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["left_coverage"] == 1.0
        assert payload[0]["right_coverage"] == 0.75

    def test_an_unmeasurable_pair_is_an_error(self, monkeypatch, capsys):
        """``None`` is "not measured", which is not a zero-overlap answer."""
        introspector = _RecordingIntrospector({"estimate_join_coverage": None})

        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                introspector,
                _name_required_argv(
                    "join-coverage", ["--column", "BUYER_ID"] + self._right_flags
                ),
            )

        assert excinfo.value.code == 1
        assert "no coverage could be measured" in capsys.readouterr().err


class TestTheArgumentRules:
    """The rules the CLI owns: a NAME and a flag are read, refused or required."""

    @pytest.mark.parametrize(
        "type_", ["ddl", "column-profiles", "value-samples", "join-coverage"]
    )
    def test_a_missing_table_name_exits_one(self, type_, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(monkeypatch, _RecordingIntrospector(), ["introspect", type_] + CONNECTION)
        assert excinfo.value.code == 1
        assert "Table name is required" in capsys.readouterr().err

    def test_a_missing_column_exits_one(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                _name_required_argv("value-samples"),
            )
        assert excinfo.value.code == 1
        assert "--column is required" in capsys.readouterr().err

    def test_a_missing_right_pair_exits_one(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                _name_required_argv("join-coverage", ["--column", "BUYER_ID"]),
            )
        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "--right-table" in err
        assert "--right-column" in err

    def test_a_flag_the_type_does_not_read_is_refused(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                ["introspect", "tables", "--column", "status"] + CONNECTION,
            )
        assert excinfo.value.code == 2
        assert "takes no --column" in capsys.readouterr().err

    def test_the_join_flags_are_refused_outside_join_coverage(self, capsys, monkeypatch):
        with pytest.raises(SystemExit) as excinfo:
            _run_sync(
                monkeypatch,
                _RecordingIntrospector(),
                ["introspect", "tables", "--right-table", "users"] + CONNECTION,
            )
        assert excinfo.value.code == 2
        assert "takes no --right-table" in capsys.readouterr().err

    def test_the_stray_flag_is_refused_before_the_connection(self, monkeypatch):
        """A refused flag never reaches the introspector, so nothing is rendered."""
        introspector = _RecordingIntrospector()

        with pytest.raises(SystemExit):
            _run_sync(
                monkeypatch,
                introspector,
                ["introspect", "tables", "--column", "status"] + CONNECTION,
            )

        assert introspector.calls == []


class TestTheCapabilityGate:
    """The switch is what the run consults, and it is consulted before the work.

    Six of the nine families are ones this dialect cannot answer, and the
    earlier behaviour was to run the branch anyway -- which produced an empty
    listing that read as "this database has none". Refusing first is what makes
    the two answers distinguishable, so the gate is asserted against the live
    dialect and against a stub whose switch answers ``False``.
    """

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_every_type_names_a_switch_the_dialect_declares(self, type_):
        switch = introspect_cli._TYPE_CAPABILITIES[type_]
        assert switch == NEW_FAMILIES[type_]
        assert hasattr(SnowflakeDialect, switch)

    @pytest.mark.parametrize("type_", GATED_FAMILIES)
    def test_a_family_this_dialect_cannot_answer_exits_two(self, type_, capsys):
        """The live dialect answers the switch, and the gate follows it."""
        import argparse as _argparse

        class _Backend:
            dialect = SnowflakeDialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), _argparse.Namespace(type=type_))

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_a_family_the_server_refuses_is_refused(self, type_, capsys):
        """A switch that answers ``False`` refuses, whatever the family."""
        import argparse as _argparse

        class _Dialect:
            pass

        setattr(_Dialect, NEW_FAMILIES[type_], staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(_Backend(), _argparse.Namespace(type=type_))

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", GATED_FAMILIES)
    def test_the_gate_never_reaches_the_introspector(self, type_, monkeypatch):
        """A refused family is not asked, so no statement is ever rendered.

        A real dialect sits behind the run this time, so the inherited
        ``False`` is what the gate reads -- the stub above answers everything,
        and this is the assertion that a live run refuses before it reaches
        the introspector rather than rendering a statement on a catalogue
        Snowflake does not have.
        """
        introspector = _RecordingIntrospector()

        argv = ["introspect", type_] + CONNECTION
        if type_ in ("ddl", "column-profiles", "value-samples", "join-coverage"):
            argv += ["orders"]
        if type_ in ("value-samples", "join-coverage"):
            argv += ["--column", "BUYER_ID"]
        if type_ == "join-coverage":
            argv += ["--right-table", "users", "--right-column", "ID"]

        with pytest.raises(SystemExit):
            _run_sync(monkeypatch, introspector, argv, dialect=SnowflakeDialect)

        assert introspector.calls == []

    @pytest.mark.parametrize(
        "type_", ["column-profiles", "value-samples", "join-coverage"]
    )
    def test_the_families_the_dialect_answers_pass_the_real_gate(
        self, type_, monkeypatch
    ):
        """The three families are genuinely answerable, so the gate lets them by.

        This is the one place the branch's reachability is asserted against
        the real dialect rather than an answer-everything stub: the switch
        answers ``True`` here, so the run gets as far as the introspector.
        """
        introspector = _RecordingIntrospector(
            {
                "list_column_data_profiles": [],
                "sample_column_values": [],
                "estimate_join_coverage": None,
            }
        )

        argv = ["introspect", type_, "orders"] + CONNECTION
        if type_ in ("value-samples", "join-coverage"):
            argv += ["--column", "BUYER_ID"]
        if type_ == "join-coverage":
            argv += ["--right-table", "users", "--right-column", "ID"]

        try:
            _run_sync(monkeypatch, introspector, argv, dialect=SnowflakeDialect)
        except SystemExit as exc:
            # ``join-coverage`` answers ``None`` with the stub's result, and
            # that is the family's own "cannot be measured", exit 1 -- the
            # capability refusal would have been exit 2.
            assert exc.code == 1

        assert len(introspector.calls) == 1


class TestTheAsyncPath:
    """The second dispatch chain must ask the same question the first one does."""

    @pytest.mark.parametrize(
        "type_, method, extra, expected",
        [
            ("unused-indexes", "list_unused_indexes", [], ((), {"schema": None})),
            ("table-stats", "list_table_usage_stats", [], ((), {"schema": None})),
            ("runtime", "list_runtime_metrics", [], ((), {"schema": None})),
            ("index-stats", "list_index_usage_stats", [], ((), {"schema": None})),
            (
                "dependencies",
                "list_object_dependencies",
                ["posts"],
                ((), {"object_name": "posts", "schema": None}),
            ),
            (
                "ddl",
                "get_ddl_statement",
                ["orders"],
                (("orders",), {"object_type": None, "schema": None}),
            ),
            (
                "column-profiles",
                "list_column_data_profiles",
                ["orders"],
                (("orders",), {"schema": None}),
            ),
            (
                "value-samples",
                "sample_column_values",
                ["orders", "--column", "status", "--limit", "5"],
                (("orders", "status"), {"limit": 5, "schema": None}),
            ),
            (
                "join-coverage",
                "estimate_join_coverage",
                [
                    "orders",
                    "--column",
                    "BUYER_ID",
                    "--right-table",
                    "users",
                    "--right-column",
                    "ID",
                ],
                (("orders", "BUYER_ID", "users", "ID"), {"schema": None}),
            ),
        ],
    )
    def test_the_async_branch_calls_the_same_method_with_the_same_arguments(
        self, type_, method, extra, expected, monkeypatch
    ):
        # The one family whose answer is a single row rather than a listing
        # needs an actual statement, because the branch reads a field off it.
        results = {method: []}
        if method == "get_ddl_statement":
            results[method] = DDLStatement(
                schema=None,
                object_type="TABLE",
                object_name="orders",
                ddl="CREATE TABLE ORDERS (ID NUMBER)",
                native=True,
            )
        if method == "estimate_join_coverage":
            results[method] = JoinCoverage(
                left_table="orders",
                left_column="BUYER_ID",
                right_table="users",
                right_column="ID",
                left_coverage=1.0,
                right_coverage=0.75,
            )
        introspector = _AsyncRecordingIntrospector(results)

        _run_async(monkeypatch, introspector, ["introspect", type_] + extra + CONNECTION)

        assert introspector.calls == [(method, expected[0], expected[1])]


class TestTheTypeSurfaceExtension:
    def test_the_advertised_types_are_the_capability_mapping(self):
        """One source for the list: the mapping, not a second hand-written copy."""
        assert list(introspect_cli._TYPE_CAPABILITIES) == introspect_cli.INTROSPECT_TYPES

    @pytest.mark.parametrize("type_", list(NEW_FAMILIES))
    def test_every_listed_type_parses(self, type_):
        assert (
            build_parser().parse_args(["introspect", type_] + CONNECTION).type == type_
        )

    def test_the_help_lists_every_new_family(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for type_ in NEW_FAMILIES:
            assert type_ in out

    def test_the_new_flags_parse_only_for_their_own_types(self):
        args = build_parser().parse_args(
            ["introspect", "value-samples", "orders", "--column", "status", "--limit", "3"]
            + CONNECTION
        )
        assert (args.column, args.limit) == ("status", 3)
