# tests/rhosocial/activerecord_snowflake_test/feature/backend/cli/test_introspect_catalog_families_cli.py
"""CLI wiring for ``routines`` / ``sequences`` / the catalog object types.

No server is needed here. The backend is stubbed and the introspector records
each call, so a branch that reaches the wrong method, or drops the schema
argument, fails here rather than showing up as a plausible-looking listing.

The advertised type list derives from ``_TYPE_CAPABILITIES``; every new type is
also checked against the dialect switch it names, so a family cannot be offered
without an answer behind it.
"""

import argparse
import json
from typing import List, Optional

import pytest

from rhosocial.activerecord.backend.impl.snowflake.cli import introspect as introspect_cli
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.introspection import (
    SnowflakeCatalogObjectInfo,
    SnowflakeRoutineInfo,
)
from rhosocial.activerecord.backend.introspection.types import SequenceInfo

#: The new CLI type -> the introspector method it reaches.
NEW_TYPES = {
    "routines": "list_routines",
    "sequences": "list_sequences",
    "stages": "list_stages",
    "file-formats": "list_file_formats",
    "pipes": "list_pipes",
    "tasks": "list_tasks",
    "streams": "list_streams",
}

#: The switch each type is gated on.
NEW_SWITCHES = {
    "routines": "supports_routine_introspection",
    "sequences": "supports_sequence_introspection",
    "stages": "supports_stage_introspection",
    "file-formats": "supports_file_format_introspection",
    "pipes": "supports_pipe_introspection",
    "tasks": "supports_task_introspection",
    "streams": "supports_stream_introspection",
}

CONNECTION = ["--account", "acct"]


class _RecordingIntrospector:
    def __init__(self, results: Optional[dict] = None) -> None:
        self.results = results or {}
        self.calls = []

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AsyncRecordingIntrospector(_RecordingIntrospector):
    def __getattr__(self, name: str):
        async def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.results.get(name)

        return call


class _AllTrueDialect:
    def __getattr__(self, name: str):
        if name.startswith("supports_"):
            return lambda: True
        raise AttributeError(name)


class _RecordingProvider:
    def __init__(self) -> None:
        self.results: List[object] = []

    def display_results(self, data, title=None):
        self.results.append((title, data))

    def display_connection_error(self, error):
        pass

    def display_query_error(self, error):
        pass


def build_parser():
    top = argparse.ArgumentParser()
    subparsers = top.add_subparsers(dest="command")
    introspect_cli.create_parser(subparsers)
    return top


def _patch_backend(monkeypatch, introspector, dialect=None, use_async=False):
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
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect)
    introspect_cli.handle(build_parser().parse_args(argv))


def _run_async(monkeypatch, introspector, argv, dialect=None):
    monkeypatch.setattr(
        introspect_cli,
        "create_provider",
        lambda fmt, ascii_borders=False: _RecordingProvider(),
    )
    _patch_backend(monkeypatch, introspector, dialect=dialect, use_async=True)
    introspect_cli.handle(build_parser().parse_args(argv + ["--use-async"]))


def _run_with_real_provider(monkeypatch, introspector, argv):
    _patch_backend(monkeypatch, introspector)
    introspect_cli.handle(build_parser().parse_args(argv))


def _sample_result(method: str):
    if method == "list_routines":
        return [
            SnowflakeRoutineInfo(
                name="ADD_ONE",
                kind="FUNCTION",
                schema="PUBLIC",
                language="SQL",
                argument_signature="(NUMBER)",
                return_type="NUMBER",
                owner="SYSADMIN",
                comment="adds one",
            )
        ]
    if method == "list_sequences":
        return [
            SequenceInfo(
                name="ORDERS_ID_SEQ",
                schema="PUBLIC",
                data_type="NUMBER",
                start_value=1,
                increment=1,
                extra={"snowflake_owner": "SYSADMIN", "snowflake_next_value": 4},
            )
        ]
    return [
        SnowflakeCatalogObjectInfo(
            name="OBJECT_1",
            kind="STAGE",
            catalog="MY_DB",
            schema="PUBLIC",
            owner="SYSADMIN",
            comment="sample",
            extra={"stage_url": "s3://bucket/path/"},
        )
    ]


# ================================================================== #
# Argument parsing and NAME rules
# ================================================================== #


class TestCatalogFamilyArguments:
    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_every_new_type_is_advertised_and_parses(self, type_):
        assert type_ in introspect_cli.INTROSPECT_TYPES
        args = build_parser().parse_args(["introspect", type_] + CONNECTION)
        assert args.type == type_
        assert args.name is None
        assert args.use_async is False

    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_a_name_is_refused(self, type_, capsys):
        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._refuse_name(
                build_parser().parse_args(["introspect", type_, "orders"] + CONNECTION)
            )
        assert excinfo.value.code == 2
        assert "takes no name" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_the_refusal_happens_before_anything_connects(self, type_, monkeypatch):
        introspector = _RecordingIntrospector()
        with pytest.raises(SystemExit):
            _run_sync(
                monkeypatch,
                introspector,
                ["introspect", type_, "orders"] + CONNECTION,
            )
        assert introspector.calls == []

    def test_the_new_types_are_in_the_no_name_rule(self):
        assert set(NEW_TYPES) <= set(introspect_cli._NO_NAME_TYPES)

    def test_the_help_lists_every_new_type(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["introspect", "--help"])
        out = capsys.readouterr().out
        for type_ in NEW_TYPES:
            assert type_ in out

    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_the_advertised_list_is_the_capability_mapping(self, type_):
        assert list(introspect_cli._TYPE_CAPABILITIES) == introspect_cli.INTROSPECT_TYPES


# ================================================================== #
# Capability gate
# ================================================================== #


class TestCatalogFamilyCapabilities:
    @pytest.mark.parametrize("type_, switch", list(NEW_SWITCHES.items()))
    def test_each_type_names_a_switch_the_dialect_declares(self, type_, switch):
        assert introspect_cli._TYPE_CAPABILITIES[type_] == switch
        assert hasattr(SnowflakeDialect, switch)
        assert getattr(SnowflakeDialect(), switch)() is True

    @pytest.mark.parametrize("type_, switch", list(NEW_SWITCHES.items()))
    def test_a_switch_that_answers_false_refuses(self, type_, switch, capsys):
        class _Dialect:
            pass

        setattr(_Dialect, switch, staticmethod(lambda: False))

        class _Backend:
            dialect = _Dialect()

        with pytest.raises(SystemExit) as excinfo:
            introspect_cli._require_capability(
                _Backend(), argparse.Namespace(type=type_)
            )

        assert excinfo.value.code == 2
        assert "not supported by this server" in capsys.readouterr().err

    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_the_real_dialect_passes_the_gate(self, type_, monkeypatch):
        introspector = _RecordingIntrospector(
            {NEW_TYPES[type_]: _sample_result(NEW_TYPES[type_])}
        )
        # No SystemExit: the switch is True on the live dialect.
        _run_sync(
            monkeypatch,
            introspector,
            ["introspect", type_] + CONNECTION,
            dialect=SnowflakeDialect,
        )
        assert len(introspector.calls) == 1


# ================================================================== #
# Synchronous dispatch
# ================================================================== #


class TestSyncCatalogFamilyDispatch:
    @pytest.mark.parametrize(
        "type_, method, title",
        [
            ("routines", "list_routines", "Routines"),
            ("sequences", "list_sequences", "Sequences"),
            ("stages", "list_stages", "Stages"),
            ("file-formats", "list_file_formats", "File Formats"),
            ("pipes", "list_pipes", "Pipes"),
            ("tasks", "list_tasks", "Tasks"),
            ("streams", "list_streams", "Streams"),
        ],
    )
    def test_the_family_reaches_its_method_with_the_schema_slot(
        self, type_, method, title, monkeypatch
    ):
        introspector = _RecordingIntrospector({method: _sample_result(method)})

        _run_sync(monkeypatch, introspector, ["introspect", type_] + CONNECTION)

        assert introspector.calls == [(method, (), {"schema": None})]

    @pytest.mark.parametrize("type_", list(NEW_TYPES))
    def test_the_result_reaches_the_provider(self, type_, monkeypatch):
        method = NEW_TYPES[type_]
        introspector = _RecordingIntrospector({method: _sample_result(method)})
        provider = _RecordingProvider()

        monkeypatch.setattr(
            introspect_cli,
            "create_provider",
            lambda fmt, ascii_borders=False: provider,
        )
        _patch_backend(monkeypatch, introspector)
        introspect_cli.handle(
            build_parser().parse_args(["introspect", type_] + CONNECTION)
        )

        assert len(provider.results) == 1
        title, data = provider.results[0]
        assert data
        assert title is not None

    def test_routines_output_is_json_serialisable(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_routines": _sample_result("list_routines")}
        )
        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "routines", "-o", "json"] + CONNECTION,
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["name"] == "ADD_ONE"
        assert payload[0]["kind"] == "FUNCTION"
        assert payload[0]["language"] == "SQL"
        assert payload[0]["argument_signature"] == "(NUMBER)"
        assert payload[0]["return_type"] == "NUMBER"

    def test_sequences_output_keeps_core_fields_and_extras(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_sequences": _sample_result("list_sequences")}
        )
        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "sequences", "-o", "json"] + CONNECTION,
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["start_value"] == 1
        assert payload[0]["increment"] == 1
        assert payload[0]["extra"]["snowflake_next_value"] == 4

    def test_catalog_output_keeps_the_stable_shape(self, monkeypatch, capsys):
        introspector = _RecordingIntrospector(
            {"list_stages": _sample_result("list_stages")}
        )
        _run_with_real_provider(
            monkeypatch,
            introspector,
            ["introspect", "stages", "-o", "json"] + CONNECTION,
        )

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["kind"] == "STAGE"
        assert payload[0]["schema"] == "PUBLIC"
        assert payload[0]["extra"]["stage_url"] == "s3://bucket/path/"


# ================================================================== #
# Asynchronous dispatch
# ================================================================== #


class TestAsyncCatalogFamilyDispatch:
    @pytest.mark.parametrize("type_, method", list(NEW_TYPES.items()))
    def test_async_reaches_the_same_method_with_the_same_arguments(
        self, type_, method, monkeypatch
    ):
        introspector = _AsyncRecordingIntrospector(
            {method: _sample_result(method)}
        )

        _run_async(monkeypatch, introspector, ["introspect", type_] + CONNECTION)

        assert introspector.calls == [(method, (), {"schema": None})]

    async def test_async_result_reaches_the_provider(self):
        introspector = _AsyncRecordingIntrospector(
            {"list_tasks": [SnowflakeCatalogObjectInfo(name="T", kind="TASK")]}
        )
        args = build_parser().parse_args(
            ["introspect", "tasks", "--use-async"] + CONNECTION
        )
        backend = _FakeAsyncBackend(introspector)
        provider = _RecordingProvider()

        await introspect_cli._handle_introspect_async(args, backend, provider)

        provider_results = provider.results
        assert provider_results[0][0] == "Tasks"
        assert provider_results[0][1][0]["name"] == "T"


class _FakeAsyncBackend:
    """The async handler's backend shape: awaited connect/disconnect."""

    def __init__(self, introspector):
        self.introspector = introspector
        self._connection = None

    async def connect(self):
        pass

    async def disconnect(self):
        pass
