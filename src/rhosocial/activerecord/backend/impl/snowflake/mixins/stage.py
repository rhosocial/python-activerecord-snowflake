# src/rhosocial/activerecord/backend/impl/snowflake/mixins/stage.py
"""SnowflakeStageMixin — stage (data staging area) support."""

from typing import Optional


class SnowflakeStageMixin:
    """Mixin for Snowflake stage (data staging area) support."""

    def supports_stages(self) -> bool:
        """Snowflake supports stages."""
        return True

    def format_copy_into_table(
        self, table: str, stage: str, file_format: Optional[str] = None
    ) -> str:
        """Format COPY INTO table FROM stage statement."""
        sql = f'COPY INTO {table} FROM @{stage}'
        if file_format:
            sql += f' FILE_FORMAT = ({file_format})'
        return sql