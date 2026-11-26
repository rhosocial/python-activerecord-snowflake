# tests/rhosocial/activerecord_snowflake_test/feature/backend/construct/cli/test_introspect_offline.py
"""Pure-mock unit tests for ``cli.introspect`` (offline, sync paths only).

Nothing in this module opens a connection or imports a driver: the backend, the
introspector and the output provider are all fakes.  The aim is to pin the
parts the helper-level tests do not reach -- the parser contract, the argument
helpers, serialisation, and every synchronous dispatch branch of
``_handle_introspect_sync`` -- while deliberately leaving the pseudo-async
wrapper alone (the connector is sync-only, so the async chain is a thread-pool
detail rather than a thing to unit test here).
"""

import argparse
from dataclasses import dataclass
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from rhosocial.activerecord.backend.errors import ConnectionError, QueryError
from rhosocial.activerecord.backend.impl.snowflake.cli import introspect as mod
from rhosocial.activerecord.backend.impl.snowflake.cli import output as cli_output

#: An argv skeleton that satisfies the "account or database" gate.
CONNECTION = ["--account", "acct"]


def build_parser():
    """Build a real top-level parser carrying the introspect subparser."""
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    mod.create_parser(subparsers)
    return top


def parse(*argv):
    """Parse an introspect invocation, with the connection gate pre-satisfied."""
    return build_parser().parse_args(["introspect", *argv, *CONNECTION])


class _StubIntrospector:
    """Records every call and returns a declared result (``[]`` by default)."""

    def __init__(self, **results):
        self.results = results
        self.calls = []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name, [])

        return call


def make_backend(results=None, connected=True):
    """A fake backend: no dialect gate, a stub introspector, a fake connection."""
    backend = MagicMock()
    backend.dialect = None  # _require_capability returns early for a stub
    backend.introspector = _StubIntrospector(**(results or {}))
    backend._connection = object() if connected else None
    return backend


def make_provider():
    """A recording output provider as a MagicMock."""
    return MagicMock()


class _Colour(Enum):
    RED = "red"
    BLUE = "blue"


@dataclass
class _Point:
    x: int
    y: int


class _Model:
    """Minimal pydantic-shaped object: ``model_dump`` with a mode keyword."""

    def model_dump(self, mode=None):
        return {"mode": mode, "value": 7}


class _ModelNoMode:
    """A ``model_dump`` that rejects ``mode``, exercising the TypeError branch."""

    def model_dump(self, mode=None):
        if mode is not None:
            raise TypeError("no mode here")
        return {"value": 9}


# ================================================================== #
# Parser contract
# ================================================================== #


class TestCreateParser:
    def test_defaults(self):
        args = parse("tables")
        assert args.type == "tables"
        assert args.name is None
        assert args.output == "table"
        assert args.include_system is False
        assert args.rich_ascii is False
        assert args.use_async is False
        assert (args.column, args.right_table, args.right_column, args.limit) == (
            None,
            None,
            None,
            None,
        )

    def test_type_choices_are_the_capability_mapping(self):
        top = build_parser()
        subparsers = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
        subparser = subparsers.choices["introspect"]
        action = next(a for a in subparser._actions if a.dest == "type")
        assert action.choices == mod.INTROSPECT_TYPES

    @pytest.mark.parametrize("itype", mod.INTROSPECT_TYPES)
    def test_every_advertised_type_parses(self, itype):
        assert parse(itype).type == itype

    def test_an_unknown_type_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["introspect", "triggers", *CONNECTION])
        assert exc.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    @pytest.mark.parametrize("fmt", cli_output.OUTPUT_CHOICES)
    def test_output_choices_parse(self, fmt):
        assert parse("tables", "-o", fmt).output == fmt

    def test_an_unknown_output_exits_two(self):
        with pytest.raises(SystemExit):
            parse("tables", "-o", "yaml")

    @pytest.mark.parametrize("flag", ["--include-system", "--rich-ascii", "--use-async"])
    def test_store_true_flags(self, flag):
        assert getattr(parse("tables", flag), flag.lstrip("-").replace("-", "_")) is True

    def test_limit_is_an_integer(self):
        assert parse("value-samples", "orders", "--column", "c", "--limit", "5").limit == 5
        with pytest.raises(SystemExit):
            parse("value-samples", "orders", "--column", "c", "--limit", "many")

    def test_join_and_sample_flags_are_strings(self):
        args = parse(
            "join-coverage",
            "orders",
            "--column",
            "buyer_id",
            "--right-table",
            "users",
            "--right-column",
            "id",
        )
        assert (args.column, args.right_table, args.right_column) == (
            "buyer_id",
            "users",
            "id",
        )

    def test_version_argument_is_not_offered_here(self):
        """``--version`` belongs to ``info``; a typo must not be silently kept."""
        with pytest.raises(SystemExit):
            parse("tables", "--version", "8.0.0")

    def test_help_lists_every_type_and_the_examples(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for itype in mod.INTROSPECT_TYPES:
            assert itype in out
        assert "Examples:" in out


# ================================================================== #
# Pure helpers
# ================================================================== #


class TestSerialiseForOutput:
    @pytest.mark.parametrize("value", [None, "s", 3, 1.5, True])
    def test_primitives_pass_through(self, value):
        assert mod._serialize_for_output(value) is value

    def test_a_dict_is_recursively_serialised(self):
        obj = {"a": [_Colour.RED, _Point(1, 2)], "b": None}
        assert mod._serialize_for_output(obj) == {
            "a": ["red", {"x": 1, "y": 2}],
            "b": None,
        }

    def test_a_tuple_becomes_a_list(self):
        assert mod._serialize_for_output((1, "a")) == [1, "a"]

    def test_an_enum_becomes_its_value(self):
        assert mod._serialize_for_output(_Colour.BLUE) == "blue"

    def test_a_dataclass_becomes_a_dict(self):
        assert mod._serialize_for_output(_Point(1, 2)) == {"x": 1, "y": 2}

    def test_a_model_dump_with_mode_is_used(self):
        assert mod._serialize_for_output(_Model()) == {"mode": "json", "value": 7}

    def test_a_model_dump_that_rejects_mode_falls_back(self):
        assert mod._serialize_for_output(_ModelNoMode()) == {"value": 9}

    def test_an_unknown_object_falls_back_to_str(self):
        class Opaque:
            def __str__(self):
                return "opaque"

        assert mod._serialize_for_output(Opaque()) == "opaque"


class TestValueSampleArguments:
    @pytest.mark.parametrize("limit,expected", [(None, {}), (0, {"limit": 0}), (25, {"limit": 25})])
    def test_limit_is_forwarded_only_when_supplied(self, limit, expected):
        assert mod._value_sample_arguments(argparse.Namespace(limit=limit)) == expected

    def test_a_namespace_without_limit_is_allowed(self):
        """Hand-built namespaces used by callers carry no flags at all."""
        assert mod._value_sample_arguments(argparse.Namespace()) == {}


class TestRequireCapability:
    def test_an_unknown_type_has_no_switch(self):
        backend = MagicMock()
        mod._require_capability(backend, argparse.Namespace(type="not-a-type"))

    def test_a_stub_backend_without_a_dialect_is_allowed(self):
        backend = MagicMock(spec=[])
        mod._require_capability(backend, argparse.Namespace(type="tables"))

    def test_a_missing_switch_on_the_dialect_is_allowed(self):
        backend = MagicMock()
        backend.dialect = MagicMock(spec=[])
        mod._require_capability(backend, argparse.Namespace(type="tables"))

    def test_a_supported_switch_returns(self):
        backend = MagicMock()
        backend.dialect.supports_table_introspection.return_value = True
        mod._require_capability(backend, argparse.Namespace(type="tables"))

    @pytest.mark.parametrize("itype", mod.INTROSPECT_TYPES)
    def test_a_refused_switch_exits_two(self, itype, capsys):
        backend = MagicMock()
        backend.dialect = MagicMock(spec=[mod._TYPE_CAPABILITIES[itype]])
        getattr(backend.dialect, mod._TYPE_CAPABILITIES[itype]).return_value = False
        with pytest.raises(SystemExit) as exc:
            mod._require_capability(backend, argparse.Namespace(type=itype))
        assert exc.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err


class TestRefuseName:
    def test_a_type_that_takes_a_name_is_unaffected(self):
        mod._refuse_name(argparse.Namespace(type="columns", name="orders"))

    def test_no_name_on_a_family_type_is_unaffected(self):
        mod._refuse_name(argparse.Namespace(type="tables", name=None))

    @pytest.mark.parametrize("itype", mod._NO_NAME_TYPES)
    def test_a_name_on_a_family_type_exits_two(self, itype, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_name(argparse.Namespace(type=itype, name="analytics"))
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "takes no name" in err
        assert "analytics" in err


class TestRequireName:
    def test_a_family_type_does_not_need_a_name(self):
        mod._require_name(argparse.Namespace(type="tables", name=None))

    def test_a_present_name_satisfies_the_rule(self):
        mod._require_name(argparse.Namespace(type="columns", name="orders"))

    @pytest.mark.parametrize("itype", mod._TABLE_NAME_TYPES)
    def test_a_missing_name_exits_one(self, itype, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._require_name(argparse.Namespace(type=itype, name=None))
        assert exc.value.code == 1
        assert "Table name is required" in capsys.readouterr().err


class TestRefuseUnusedArguments:
    def test_a_type_with_no_type_options_accepts_a_bare_namespace(self):
        mod._refuse_unused_arguments(argparse.Namespace(type="tables"))

    def test_a_missing_required_column_exits_one(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(argparse.Namespace(type="value-samples", column=None))
        assert exc.value.code == 1
        assert "--column is required" in capsys.readouterr().err

    def test_a_stray_join_flag_exits_two(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(
                argparse.Namespace(type="value-samples", column="c", right_table="users")
            )
        assert exc.value.code == 2
        assert "takes no --right-table" in capsys.readouterr().err

    def test_multiple_missing_join_flags_are_all_named(self, capsys):
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(
                argparse.Namespace(
                    type="join-coverage", column="c", right_table=None, right_column=None
                )
            )
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "--right-table" in err and "--right-column" in err

    @pytest.mark.parametrize("attribute,flag", list(mod._TYPE_OPTION_FLAGS.items()))
    def test_a_stray_flag_is_refused_on_tables(self, attribute, flag, capsys):
        args = argparse.Namespace(type="tables")
        setattr(args, attribute, "x")
        with pytest.raises(SystemExit) as exc:
            mod._refuse_unused_arguments(args)
        assert exc.value.code == 2
        assert f"takes no {flag}" in capsys.readouterr().err

    def test_an_empty_string_does_not_count_as_given(self):
        mod._refuse_unused_arguments(argparse.Namespace(type="tables", column=""))


# ================================================================== #
# handle() dispatch -- backend and I/O seams are mocked
# ================================================================== #


class TestHandleDispatch:
    def _args(self, **overrides):
        values = dict(
            output="table",
            rich_ascii=True,
            account="acct",
            database=None,
            type="tables",
            use_async=False,
        )
        values.update(overrides)
        values["name"] = values.get("name")
        return argparse.Namespace(**values)

    def test_sync_path_builds_backend_and_calls_the_sync_handler(self):
        args = self._args()
        backend = MagicMock()
        provider = MagicMock()
        seen = {}

        def fake_sync(a, b, c):
            seen["args"] = (a, b, c)

        with patch.object(mod, "create_provider", return_value=provider) as cp, patch.object(
            mod, "resolve_connection_config_from_args", return_value="CFG"
        ) as resolve, patch.object(mod, "SnowflakeBackend", return_value=backend) as factory, patch.object(
            mod, "_handle_introspect_sync", side_effect=fake_sync
        ):
            mod.handle(args)

        cp.assert_called_once_with("table", ascii_borders=True)
        resolve.assert_called_once_with(args)
        factory.assert_called_once_with(connection_config="CFG")
        assert seen["args"] == (args, backend, provider)

    def test_missing_account_and_database_exits_before_connecting(self, capsys):
        args = self._args(account=None, database=None)
        with patch.object(mod, "create_provider", return_value=MagicMock()), patch.object(
            mod, "SnowflakeBackend"
        ) as factory:
            with pytest.raises(SystemExit) as exc:
                mod.handle(args)
        assert exc.value.code == 1
        assert "--account and/or --database" in capsys.readouterr().err
        factory.assert_not_called()

    def test_database_alone_satisfies_the_connection_gate(self):
        args = self._args(account=None, database="ANALYTICS")
        with patch.object(mod, "create_provider", return_value=MagicMock()), patch.object(
            mod, "resolve_connection_config_from_args", return_value="CFG"
        ), patch.object(mod, "SnowflakeBackend", return_value=MagicMock()), patch.object(
            mod, "_handle_introspect_sync"
        ) as sync:
            mod.handle(args)
        sync.assert_called_once()

    def test_argument_helpers_run_before_the_backend_is_built(self):
        args = self._args()
        with patch.object(mod, "create_provider", return_value=MagicMock()), patch.object(
            mod, "_refuse_name", side_effect=SystemExit(2)
        ) as refuse, patch.object(mod, "_require_name") as require, patch.object(
            mod, "_refuse_unused_arguments"
        ) as unused, patch.object(mod, "SnowflakeBackend") as factory:
            with pytest.raises(SystemExit):
                mod.handle(args)
        refuse.assert_called_once_with(args)
        require.assert_not_called()
        unused.assert_not_called()
        factory.assert_not_called()

    def test_all_three_argument_helpers_are_consulted(self):
        args = self._args()
        with patch.object(mod, "create_provider", return_value=MagicMock()), patch.object(
            mod, "_refuse_name"
        ) as refuse, patch.object(mod, "_require_name") as require, patch.object(
            mod, "_refuse_unused_arguments"
        ) as unused, patch.object(mod, "resolve_connection_config_from_args", return_value="CFG"), patch.object(
            mod, "SnowflakeBackend", return_value=MagicMock()
        ), patch.object(mod, "_handle_introspect_sync"):
            mod.handle(args)
        refuse.assert_called_once_with(args)
        require.assert_called_once_with(args)
        unused.assert_called_once_with(args)


# ================================================================== #
# Synchronous dispatch branches -- every type, every title
# ================================================================== #


class TestSyncBranchDispatch:
    @pytest.mark.parametrize(
        "itype,name,method,args,kwargs,title",
        [
            ("tables", None, "list_tables", (), {"schema": None, "include_system": False}, "Tables"),
            ("views", None, "list_views", (), {"schema": None}, "Views"),
            ("views", "v1", "get_view_info", ("v1",), {"schema": None}, "View v1"),
            ("columns", "t", "list_columns", ("t",), {"schema": None}, "Columns of t"),
            ("indexes", "t", "list_indexes", ("t",), {"schema": None}, "Indexes of t"),
            (
                "foreign-keys",
                "t",
                "list_foreign_keys",
                ("t",),
                {"schema": None},
                "Foreign Keys of t",
            ),
            (
                "table-storage-metrics",
                "t",
                "get_table_storage_metrics",
                ("t",),
                {"schema": None},
                "Storage Metrics of t",
            ),
            ("database", None, "get_database_info", (), {}, "Database Info"),
            ("databases", None, "list_databases", (), {}, "Databases"),
            ("schemas", None, "list_schema_infos", (), {"database": None}, "Schemas"),
            ("warehouses", None, "list_warehouses", (), {}, "Warehouses"),
            ("routines", None, "list_routines", (), {"schema": None}, "Routines"),
            ("sequences", None, "list_sequences", (), {"schema": None}, "Sequences"),
            ("stages", None, "list_stages", (), {"schema": None}, "Stages"),
            ("file-formats", None, "list_file_formats", (), {"schema": None}, "File Formats"),
            ("pipes", None, "list_pipes", (), {"schema": None}, "Pipes"),
            ("tasks", None, "list_tasks", (), {"schema": None}, "Tasks"),
            ("streams", None, "list_streams", (), {"schema": None}, "Streams"),
            ("unused-indexes", None, "list_unused_indexes", (), {"schema": None}, "Unused Indexes"),
            ("table-stats", None, "list_table_usage_stats", (), {"schema": None}, "Table Usage Stats"),
            ("runtime", None, "list_runtime_metrics", (), {"schema": None}, "Runtime Metrics"),
            ("index-stats", None, "list_index_usage_stats", (), {"schema": None}, "Index Usage Stats"),
            (
                "dependencies",
                None,
                "list_object_dependencies",
                (),
                {"object_name": None, "schema": None},
                "Object Dependencies",
            ),
            (
                "dependencies",
                "orders",
                "list_object_dependencies",
                (),
                {"object_name": "orders", "schema": None},
                "Dependencies of orders",
            ),
            (
                "column-profiles",
                "orders",
                "list_column_data_profiles",
                ("orders",),
                {"schema": None},
                "Column profiles of orders",
            ),
            (
                "value-samples",
                "orders",
                "sample_column_values",
                ("orders", "status"),
                {"schema": None, "limit": 3},
                "Values of orders.status",
            ),
            (
                "join-coverage",
                "orders",
                "estimate_join_coverage",
                ("orders", "buyer_id", "users", "id"),
                {"schema": None},
                "Join Coverage",
            ),
        ],
    )
    def test_each_type_calls_its_method_and_reports_its_title(
        self, itype, name, method, args, kwargs, title, capsys
    ):
        backend = make_backend()
        provider = make_provider()
        ns = argparse.Namespace(
            type=itype,
            name=name,
            include_system=False,
            database=None,
            column=(
                "buyer_id"
                if itype == "join-coverage"
                else ("status" if itype == "value-samples" else None)
            ),
            limit=3 if itype == "value-samples" else None,
            right_table="users" if itype == "join-coverage" else None,
            right_column="id" if itype == "join-coverage" else None,
        )
        mod._handle_introspect_sync(ns, backend, provider)

        assert backend.introspector.calls == [(method, args, kwargs)]
        assert provider.display_results.call_args.kwargs["title"] == title
        capsys.readouterr()  # drain the aggregate note, if any

    def test_include_system_is_forwarded_for_tables(self):
        backend = make_backend()
        ns = parse("tables", "--include-system")
        mod._handle_introspect_sync(ns, backend, make_provider())
        assert backend.introspector.calls[-1][2]["include_system"] is True

    def test_schemas_forwards_the_database_flag(self):
        backend = make_backend()
        ns = parse("schemas", "--database", "ANALYTICS")
        mod._handle_introspect_sync(ns, backend, make_provider())
        assert backend.introspector.calls[-1][2]["database"] == "ANALYTICS"

    def test_value_samples_omits_limit_when_not_given(self):
        backend = make_backend()
        ns = parse("value-samples", "orders", "--column", "status")
        mod._handle_introspect_sync(ns, backend, make_provider())
        assert "limit" not in backend.introspector.calls[-1][2]

    def test_a_missing_view_exits_one(self, capsys):
        backend = make_backend({"get_view_info": None})
        provider = make_provider()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(parse("views", "ghost"), backend, provider)
        assert exc.value.code == 1
        assert "View 'ghost' not found" in capsys.readouterr().err
        provider.display_results.assert_not_called()

    def test_a_missing_metrics_row_exits_one(self, capsys):
        backend = make_backend({"get_table_storage_metrics": None})
        provider = make_provider()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(parse("table-storage-metrics", "t"), backend, provider)
        assert exc.value.code == 1
        assert "has no storage metrics" in capsys.readouterr().err
        provider.display_results.assert_not_called()

    def test_unmeasurable_join_coverage_exits_one(self, capsys):
        backend = make_backend({"estimate_join_coverage": None})
        ns = parse(
            "join-coverage",
            "orders",
            "--column",
            "buyer_id",
            "--right-table",
            "users",
            "--right-column",
            "id",
        )
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(ns, backend, make_provider())
        assert exc.value.code == 1
        assert "no coverage could be measured" in capsys.readouterr().err

    def test_column_profile_note_goes_to_stderr(self, capsys):
        mod._handle_introspect_sync(parse("column-profiles", "orders"), make_backend(), make_provider())
        captured = capsys.readouterr()
        assert "aggregate" in captured.err
        assert captured.out == ""


class TestSyncErrorHandling:
    def test_connection_error_uses_the_provider_and_exits_one(self):
        backend = make_backend()
        backend.connect.side_effect = ConnectionError("390100")
        provider = make_provider()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(parse("tables"), backend, provider)
        assert exc.value.code == 1
        provider.display_connection_error.assert_called_once()

    def test_query_error_uses_the_provider_and_exits_one(self):
        backend = make_backend()
        backend.introspector = MagicMock()
        backend.introspector.list_tables.side_effect = QueryError("002003")
        provider = make_provider()
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(parse("tables"), backend, provider)
        assert exc.value.code == 1
        provider.display_query_error.assert_called_once()

    def test_unexpected_error_is_written_to_stderr(self, capsys):
        backend = make_backend()
        backend.introspector = MagicMock()
        backend.introspector.list_tables.side_effect = RuntimeError("boom")
        with pytest.raises(SystemExit) as exc:
            mod._handle_introspect_sync(parse("tables"), backend, make_provider())
        assert exc.value.code == 1
        assert "Error during introspection: boom" in capsys.readouterr().err

    def test_a_live_connection_is_always_disconnected(self):
        backend = make_backend(connected=True)
        backend.introspector = MagicMock()
        backend.introspector.list_tables.side_effect = RuntimeError("boom")
        with pytest.raises(SystemExit):
            mod._handle_introspect_sync(parse("tables"), backend, make_provider())
        backend.disconnect.assert_called_once()

    def test_no_connection_means_no_disconnect(self):
        backend = make_backend(connected=False)
        mod._handle_introspect_sync(parse("tables"), backend, make_provider())
        backend.disconnect.assert_not_called()
