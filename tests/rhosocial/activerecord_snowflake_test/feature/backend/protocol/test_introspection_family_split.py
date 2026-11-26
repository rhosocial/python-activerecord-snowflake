# tests/rhosocial/activerecord_snowflake_test/feature/backend/protocol/test_introspection_family_split.py
"""Guard this backend against core's four-family introspection split.

Core split the single ``IntrospectionSupport`` protocol into four families and
deleted ``supports_partition_info``. This module pins the consequences that
belong to this repository, independently of the conformance matrix:

* the legacy names are gone from the constructed dialect, core's exports and
  this repository's own source and docs;
* each family class imports from its own new core module, and the old modules
  are gone;
* the partition question resolves to the surviving metadata probe, answered
  here by the Snowflake partition mixin.
"""

import importlib
import re
from pathlib import Path

import pytest

from rhosocial.activerecord.backend.dialect import protocols as dialect_protocols
from rhosocial.activerecord.backend.dialect.protocols.introspect import (
    data_profile,
    ddl_extraction,
    operational_stats,
    structure,
)
from rhosocial.activerecord.backend.impl.snowflake.dialect import SnowflakeDialect
from rhosocial.activerecord.backend.impl.snowflake.protocols import (
    SnowflakePartitionSupport,
)

#: Repository root: protocol/ -> backend/ -> feature/ -> test package/ ->
#: rhosocial/ -> tests/ -> root.
REPO_ROOT = Path(__file__).resolve().parents[6]

#: The legacy surface, matched as whole names so the new family names -- which
#: contain "IntrospectionSupport" as a suffix -- do not trip the scan.
LEGACY_PATTERN = re.compile(
    r"\bIntrospectionSupport\b" r"|\bAsyncIntrospectionSupport\b" r"|\bsupports_partition_info\b"
)

#: (module, sync protocol name, async twin name) for the four families.
FAMILY_MODULES = [
    (structure, "StructureIntrospectionSupport", "AsyncStructureIntrospectionSupport"),
    (
        operational_stats,
        "OperationalStatsIntrospectionSupport",
        "AsyncOperationalStatsIntrospectionSupport",
    ),
    (data_profile, "DataProfileIntrospectionSupport", "AsyncDataProfileIntrospectionSupport"),
    (ddl_extraction, "DdlExtractionIntrospectionSupport", "AsyncDdlExtractionIntrospectionSupport"),
]


@pytest.fixture
def dialect():
    return SnowflakeDialect(version=(8, 0, 0))


class TestLegacyNamesAreGone:
    def test_supports_partition_info_is_absent_from_a_constructed_dialect(self, dialect):
        assert not hasattr(dialect, "supports_partition_info")

    def test_supports_partition_info_is_absent_from_every_dialect_base(self):
        for klass in SnowflakeDialect.__mro__:
            assert "supports_partition_info" not in vars(klass), (
                f"{klass.__module__}.{klass.__name__} still declares supports_partition_info"
            )

    @pytest.mark.parametrize("legacy", ["IntrospectionSupport", "AsyncIntrospectionSupport"])
    def test_the_single_protocol_names_are_not_exported(self, legacy):
        assert not hasattr(dialect_protocols, legacy)

    def test_no_source_or_doc_file_names_the_legacy_surface(self):
        offenders = []
        for relative in ("src", "docs"):
            for path in (REPO_ROOT / relative).rglob("*"):
                if path.is_dir() or "__pycache__" in path.parts:
                    continue
                if path.suffix not in {".py", ".md", ".rst", ".txt"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if LEGACY_PATTERN.search(text):
                    offenders.append(str(path.relative_to(REPO_ROOT)))
        assert not offenders, f"legacy introspection names are still referenced: {offenders}"


class TestFamiliesImportFromTheirOwnModules:
    @pytest.mark.parametrize("module,sync_name,async_name", FAMILY_MODULES)
    def test_each_family_class_comes_from_its_new_module(self, module, sync_name, async_name):
        sync = getattr(module, sync_name)
        async_ = getattr(module, async_name)
        assert sync.__module__ == module.__name__
        assert async_.__module__ == module.__name__
        assert getattr(dialect_protocols, sync_name) is sync
        assert getattr(dialect_protocols, async_name) is async_

    def test_the_family_modules_are_the_new_introspect_modules(self):
        expected = {
            structure: ".introspect.structure",
            operational_stats: ".introspect.operational_stats",
            data_profile: ".introspect.data_profile",
            ddl_extraction: ".introspect.ddl_extraction",
        }
        for module, suffix in expected.items():
            assert module.__name__.endswith(suffix), module.__name__

    @pytest.mark.parametrize("legacy", ["introspection", "async_introspection"])
    def test_the_old_single_protocol_module_is_gone(self, legacy):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(
                "rhosocial.activerecord.backend.dialect.protocols.introspect." + legacy
            )


class TestPartitionQuestionResolvesToTheMetadataProbe:
    def test_the_metadata_probe_is_the_surviving_partition_switch(self, dialect):
        assert dialect.supports_partition_metadata_introspection() is False

    def test_core_declares_the_metadata_probe_on_its_partition_protocol(self):
        own = vars(dialect_protocols.PartitionSupport)
        assert "supports_partition_metadata_introspection" in own
        assert "supports_partition_info" not in own

    def test_the_dialect_satisfies_the_partition_protocol(self, dialect):
        assert isinstance(dialect, dialect_protocols.PartitionSupport)

    def test_this_backend_answers_the_metadata_probe_itself(self, dialect):
        winner = next(
            klass
            for klass in type(dialect).__mro__
            if "supports_partition_metadata_introspection" in vars(klass)
        )
        assert winner.__module__.endswith("snowflake.mixins.partition")
        assert winner.__name__ == "SnowflakePartitionMixin"

    def test_the_snowflake_partition_protocol_names_no_legacy_switch(self):
        own = vars(SnowflakePartitionSupport)
        assert "supports_external_table_partitioning" in own
        assert "supports_partition_info" not in own
