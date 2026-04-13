from __future__ import annotations

from pgvector.sqlalchemy import HALFVEC


class AsyncpgHalfVec(HALFVEC):
    """Preserve native vector values for asyncpg instead of stringifying them.

    pgvector's stock SQLAlchemy HALFVEC type serializes values to text. That
    works for sync drivers, but with SQLAlchemy + asyncpg it causes halfvec
    parameters to arrive as strings instead of native vectors. Leaving values
    untouched lets asyncpg's registered pgvector codecs handle encoding.
    """

    cache_ok = True

    def bind_processor(self, dialect):
        if getattr(dialect, "driver", None) == "asyncpg":
            def process(value):
                return value

            return process

        return super().bind_processor(dialect)
