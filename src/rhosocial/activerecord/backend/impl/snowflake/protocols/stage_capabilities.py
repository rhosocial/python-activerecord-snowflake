# snowflake/protocols/stage_generated.py
"""Auto-generated protocol declarations (P7, 2026-09-01).

Functional-group principle: every public format_*/supports_* on a
backend mixin is declared here so dialect users can program against
the capability contract.  Regenerate via scripts/p7_generate_protocols.py
when mixins gain new public rendering methods.
"""

from typing import Any, Dict, List, Optional, Tuple

from typing import Protocol

class SnowflakeStageSupport(Protocol):
    """Auto-generated capability protocol (P7)."""

    def format_copy_into_load(self, expr: Any) -> str:
        ...  # pragma: no cover
    def format_copy_into_unload(self, expr: Any) -> str:
        ...  # pragma: no cover
    def format_file_format(self, file_format: Optional[Any]) -> Optional[str]:
        ...  # pragma: no cover
    def format_encryption(self, encryption: Any) -> str:
        ...  # pragma: no cover
